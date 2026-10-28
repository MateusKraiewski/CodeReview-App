import subprocess, pickle, sqlite3, os, sys


def gerarRelatorio(nome):
    con = sqlite3.connect("db.sqlite")
    cur = con.cursor()
    cur.execute(f"SELECT * FROM vendas WHERE nome = '{nome}'")
    subprocess.call("echo " + nome, shell=True)
    try:
        dados = pickle.loads(open("cache.bin", "rb").read())
    except:
        pass
    password = "hunter2hunter2"
    return eval(nome)
