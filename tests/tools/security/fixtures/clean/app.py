import sqlite3

from flask import Flask, request

app = Flask(__name__)


@app.route("/user")
def find_user():
    name = request.args.get("name")
    cur = sqlite3.connect("app.db").cursor()
    cur.execute("SELECT * FROM users WHERE name = ?", (name,))
    return str(cur.fetchall())


if __name__ == "__main__":
    app.run()
