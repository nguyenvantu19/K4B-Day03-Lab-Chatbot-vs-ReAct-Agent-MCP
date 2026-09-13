"""Giao diện web tối giản cho VinUni ReAct Agent.

Chạy: python src/web_app.py
Mở:  http://127.0.0.1:8001
"""

import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mcp_server import MCPAcademicServer
from prompts import MAX_ITERATIONS, REACT_AGENT_SYSTEM_PROMPT
from providers import get_llm_provider


def run_agent(question: str) -> dict:
    """Chạy một phiên ReAct và trả dữ liệu thân thiện với giao diện."""
    provider = get_llm_provider()
    mcp_server = MCPAcademicServer()
    tools = mcp_server.list_tools()
    working_query = question
    trace = []

    for step in range(1, MAX_ITERATIONS + 1):
        started_at = time.time()
        response = provider.generate_with_tools(
            working_query, tools, system_prompt=REACT_AGENT_SYSTEM_PROMPT
        )
        latency_ms = round((time.time() - started_at) * 1000, 2)
        thought = response.get("thought", "Đang suy luận...")

        if response.get("type") == "text":
            answer = response.get("content", "Không nhận được nội dung phản hồi.")
            trace.append({
                "step": step,
                "action_type": "FINAL_ANSWER",
                "thought": thought,
                "output": answer,
                "latency_ms": latency_ms,
            })
            return {"answer": answer, "trace": trace, "provider": provider.__class__.__name__}

        if response.get("type") == "tool_call":
            tool_name = response.get("tool_name")
            arguments = response.get("arguments", {})
            mcp_result = mcp_server.call_tool(tool_name, arguments)
            observation = mcp_result.get("result", {})
            trace.append({
                "step": step,
                "action_type": "TOOL_EXECUTION",
                "thought": thought,
                "tool_name": tool_name,
                "arguments": arguments,
                "observation": observation,
                "latency_ms": latency_ms,
            })
            working_query = (
                f"{question}\n\nObservation từ tool {tool_name}:\n"
                f"{json.dumps(observation, ensure_ascii=False)}\n\n"
                "Hãy dựa vào Observation trên để trả lời người dùng, không gọi lại tool."
            )
            continue

        return {"answer": "Agent trả về định dạng không hợp lệ.", "trace": trace, "provider": provider.__class__.__name__}

    answer = "Agent đã vượt quá số bước suy luận cho phép."
    return {"answer": answer, "trace": trace, "provider": provider.__class__.__name__}


PAGE = r"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>VinUni Academic ReAct Agent</title>
<style>
*{box-sizing:border-box} body{margin:0;background:#f4f7fb;color:#15233b;font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:920px;margin:0 auto;padding:44px 20px 70px} header{margin-bottom:24px} h1{margin:0;color:#0c4778;font-size:30px} .sub{color:#58708d;margin:6px 0 0}
.card{background:#fff;border:1px solid #dce5f0;border-radius:14px;padding:22px;box-shadow:0 8px 30px #253a5b0d;margin-top:16px} textarea{width:100%;min-height:105px;border:1px solid #bdcce0;border-radius:9px;padding:12px;font:inherit;resize:vertical} button{margin-top:12px;background:#087f5b;color:white;border:0;border-radius:8px;padding:11px 18px;font-weight:700;cursor:pointer} button:disabled{opacity:.6;cursor:wait}.examples button{margin:8px 8px 0 0;background:#e8f1f8;color:#16557d;font-weight:500}.label{font-size:13px;color:#60758d;text-transform:uppercase;font-weight:700;letter-spacing:.04em}.answer{white-space:pre-wrap;font-size:17px}.hidden{display:none} .step{border-left:4px solid #28a67b;padding:10px 14px;margin:12px 0;background:#f6fbf9}.step.final{border-color:#377dff;background:#f6f9ff} code{font-size:13px;white-space:pre-wrap;word-break:break-word}.status{font-size:14px;color:#60758d;margin-left:10px}
</style></head><body><main>
<header><h1>Trợ lý Học vụ VinUni</h1><p class="sub">ReAct Agent · MCP Tools · Waterfall Trace</p></header>
<section class="card"><label for="question">Câu hỏi của bạn</label><textarea id="question" placeholder="Ví dụ: Hãy tra cứu thông tin học vụ của sinh viên SV2026001."></textarea><br><button id="send">Gửi câu hỏi</button><span class="status" id="status"></span>
<div class="examples"><button data-q="Hãy tra cứu thông tin học vụ của sinh viên SV2026001.">Tra cứu học vụ</button><button data-q="Hãy đặt lịch tư vấn cho sinh viên SV2026001 vào lúc 14:00 ngày 15/09/2026.">Đặt lịch</button><button data-q="Quy chế tốt nghiệp cần bao nhiêu tín chỉ?">Câu hỏi chung</button></div></section>
<section class="card hidden" id="result"><div class="label">Câu trả lời</div><div class="answer" id="answer"></div><hr><div class="label">Waterfall trace</div><div id="trace"></div></section>
</main><script>
const q=document.querySelector('#question'),send=document.querySelector('#send'),status=document.querySelector('#status');
document.querySelectorAll('[data-q]').forEach(b=>b.onclick=()=>{q.value=b.dataset.q;q.focus()});
function escapeHtml(s){const d=document.createElement('div');d.textContent=s;return d.innerHTML}
async function ask(){if(!q.value.trim())return;send.disabled=true;status.textContent='Agent đang suy luận...';try{const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q.value.trim()})});const data=await r.json();document.querySelector('#result').classList.remove('hidden');document.querySelector('#answer').textContent=data.answer;document.querySelector('#trace').innerHTML=data.trace.map(x=>`<div class="step ${x.action_type==='FINAL_ANSWER'?'final':''}"><b>Bước ${x.step}: ${escapeHtml(x.action_type)}</b><br><span>${escapeHtml(x.thought||'')}</span><br><code>${escapeHtml(JSON.stringify(x.observation||x.output||{},null,2))}</code></div>`).join('');status.textContent='Provider: '+data.provider}catch(e){status.textContent='Có lỗi: '+e.message}finally{send.disabled=false}}
send.onclick=ask;q.addEventListener('keydown',e=>{if(e.ctrlKey&&e.key==='Enter')ask()});
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGE.encode("utf-8"))

    def do_POST(self):
        if self.path != "/api/chat":
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
            question = payload.get("question", "").strip()
            if not question:
                raise ValueError("Câu hỏi không được để trống.")
            self._send_json(200, run_agent(question))
        except (ValueError, json.JSONDecodeError) as error:
            self._send_json(400, {"error": str(error)})
        except Exception as error:
            self._send_json(500, {"error": f"Không thể chạy Agent: {error}"})

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8001), Handler)
    print("Giao diện đang chạy tại http://127.0.0.1:8001")
    print("Nhấn Ctrl+C để dừng server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng giao diện.")
    finally:
        server.server_close()
