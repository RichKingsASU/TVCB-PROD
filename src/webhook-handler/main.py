from flask import Flask, jsonify
app = Flask(__name__)

@app.get("/healthz")
def healthz():
    return jsonify(status="ok"), 200

@app.get("/")
def root():
    return "ok", 200# --- injected health routes (idempotent) ---
try:
    app  # existing Flask app?
except NameError:  # if not, create a minimal one so health works
    from flask import Flask
    app = Flask(__name__)

from flask import jsonify
import logging

def _register_if_missing(rule, view_func, methods=("GET",)):
    for r in app.url_map.iter_rules():
        if r.rule == rule:
            break
    else:
        endpoint = f"__injected_{(rule.strip('/') or 'root').replace('/','_')}"
        app.add_url_rule(rule, endpoint=endpoint, view_func=view_func, methods=list(methods))

_register_if_missing("/healthz", lambda: (jsonify(status="ok"), 200))
_register_if_missing("/",        lambda: ("ok", 200))

logging.getLogger().setLevel(logging.INFO)
for r in app.url_map.iter_rules():
    app.logger.info("route %s methods=%s", r.rule, sorted(r.methods))
# --- end injected health routes ---
