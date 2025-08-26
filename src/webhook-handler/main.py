from flask import Flask, jsonify
app = Flask(__name__)

@app.get("/healthz")
def healthz():
    return jsonify(status="ok"), 200

@app.get("/")
def root():
    return "ok", 200# --- injected health routes (idempotent) ---
try:
    app
except NameError:
    from flask import Flask
    app = Flask(__name__)
from flask import jsonify
def _reg(rule, view_func, methods=("GET",)):
    for r in app.url_map.iter_rules():
        if r.rule == rule:
            break
    else:
        app.add_url_rule(rule, endpoint=f"__inj_{(rule.strip('/') or 'root').replace('/','_')}",
                         view_func=view_func, methods=list(methods))
_reg("/healthz", lambda: (jsonify(status="ok"), 200))
_reg("/",        lambda: ("ok", 200))
# --- end injected health routes ---
