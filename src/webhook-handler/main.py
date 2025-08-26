from flask import Flask

app = Flask(__name__)

@app.get("/healthz")
def health():
    return {"status":"ok"}, 200

if __name__ == "__main__":
    import os
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",8080)))
