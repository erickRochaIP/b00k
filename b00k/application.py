import os
import requests

from flask import Flask, session, render_template, request, redirect, url_for, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker


app = Flask(__name__)

# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

#functions

def logado():
	if 'username' in session:
		return True
	else:
		return False

@app.route("/", methods=["GET", "POST"])
def index():
	if logado():
		username = session['username']
		username = username.capitalize()
		headline = "Bem Vindo, " + username
	else:
		headline = "Bem Vindo, Visitante"
	livros = db.execute("SELECT books.id, books.title, contagem.qtd FROM books JOIN (SELECT idlivro, COUNT(*) AS qtd FROM reviews GROUP BY idlivro HAVING COUNT(*)>0 ORDER BY COUNT(*)) AS contagem ON contagem.idlivro = books.id ")

	return render_template("index.html", headline=headline, logado=logado(), livros=livros)

@app.route("/login")
def login():
	return render_template("login.html", headline = "login", logado=logado())

@app.route("/logar", methods=["POST"])
def logar():
	nomeusuario = request.form.get("nomeusuario")
	senha = request.form.get("senha")
	print(nomeusuario)
	print(senha)
	if db.execute("SELECT * FROM usuarios WHERE nomeusuario = :nomeusuario AND senha = :senha", {"nomeusuario": nomeusuario, "senha":senha}).rowcount == 0:
		return render_template("erro.html", logado=logado(), message="Nome de usuario ou senha incorretos")
		db.commit()
	else:
		users = db.execute("SELECT id, nomeusuario FROM usuarios WHERE nomeusuario = :nomeusuario AND senha = :senha LIMIT 1", {"nomeusuario": nomeusuario, "senha":senha});
		for user in users:
			session['username'] = request.form['nomeusuario']
			session['id'] = user.id
			print(session['username'])
			print(session['id'])
		db.commit()
		return redirect(url_for('index'))

@app.route("/logout", methods=["POST"])
def logout():
	session.pop('username', None)
	session.pop('id', None)
	return redirect(url_for('index'))

@app.route("/cadastro")
def cadastro():
	return render_template("cadastro.html", headline = "Cadastro", message = "", logado=logado())

@app.route("/cadastrar", methods=["POST"])
def cadastrar():
	nomeusuario = request.form.get("nomeusuario")
	senha = request.form.get("senha")
	senhaConfirma = request.form.get("senhaConfirma")
	if senhaConfirma != senha:
		return render_template("cadastro.html", headline="Cadastro", message="As senhas devem ser iguais")
	db.execute("INSERT INTO usuarios (nomeusuario, senha) VALUES (:nomeusuario, :senha)", {"nomeusuario": nomeusuario, "senha": senha})
	db.commit()
	return render_template("login.html", headline = "login", logado=logado())

@app.route("/pesquisa", methods=["POST"])
def pesquisa():
	filtro = request.form.get("filtro")
	filtroSQL = "%"+filtro+"%"
	livros = db.execute("SELECT id, title FROM books WHERE title LIKE :filtroSQL OR author LIKE :filtroSQL OR isbn LIKE :filtroSQL ORDER BY title", {"filtroSQL": filtroSQL})

	if livros.rowcount == 0:
		livros="erro"

	headline = "Resultados para: " + filtro
	return render_template("pesquisa.html", headline=headline, livros=livros, logado=logado())

@app.route("/pageBook/<string:id>", methods=["GET", "POST"])
def pageBook(id):
	if not logado():
		return render_template("login.html", headline = "login", logado=logado())

	if db.execute("SELECT * FROM books WHERE id = :id", {"id": id}).rowcount == 0:
		return render_template("erro.html", logado=logado(), message = "ID de livro invalido")

	if request.method == "POST":
		resenha = request.form.get("resenha")
		nota = request.form.get("nota")
		idusuario = session['id']
		if db.execute("SELECT * FROM reviews WHERE idlivro = :idlivro AND idusuario = :idusuario", {"idlivro": id, "idusuario": idusuario}).rowcount == 0:
			db.execute("INSERT INTO reviews (resenha, nota, idlivro, idusuario) VALUES (:resenha, :nota, :idlivro, :idusuario)", {"resenha": resenha, "nota": nota, "idusuario": idusuario, "idlivro": id})
			db.commit()

	dados = db.execute("SELECT author, year, isbn, title, id FROM books WHERE id = :id", {"id" :id}).fetchone()
	reviews = db.execute("SELECT resenha, nomeusuario, nota FROM reviews JOIN usuarios ON usuarios.id = reviews.idusuario WHERE reviews.idlivro = :id", {"id": id})
	if db.execute("SELECT resenha FROM reviews WHERE idusuario = :idusuario AND idlivro = :idlivro", {"idusuario": session['id'], "idlivro": id}).rowcount == 0:
		poderesenhar = True
	else:
		poderesenhar = False

	res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "KEY", "isbns": dados.isbn})
	if res.status_code == 200:
		data = res.json()
		avg = data["books"][0]["average_rating"]
	else:
		avg = "Não disponível"

	return render_template("pageBook.html", dados=dados, reviews=reviews, logado=logado(), poderesenhar=poderesenhar, avg=avg)

@app.route("/api/<string:isbn>")
def book_api(isbn):
	book = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
	if book is None:
		return jsonify({"error": "isbn nao existe"}), 404
	res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "KEY", "isbns": isbn})
	data = res.json()
	avg = data["books"][0]["average_rating"]
	revcount = data["books"][0]["reviews_count"]
	return jsonify({
		"title": book.title,
		"author": book.author,
		"year": book.year,
		"isbn": book.isbn,
		"review_count": revcount,
		"average_score": avg
		})

if __name__ == '__main__':
	with app.app.context():
		main()