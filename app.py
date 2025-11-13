from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
import MySQLdb.cursors

app = Flask(__name__)

app.secret_key = 'unirproyecto'

app.config['MYSQL_HOST'] = '45.195.229.16'
app.config['MYSQL_USER'] = 'adminremote'
app.config['MYSQL_PASSWORD'] = 'unir'
app.config['MYSQL_DB'] = 'unir'
mysql = MySQL(app)

@app.route('/')
def home():
    if 'login' in session:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT nombre, id FROM usuarios')
        results = cursor.fetchall()
        cursor.close()
        return render_template('index.html', data=results, username=session['username'])
    
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    session.pop('_flashes', None)

    if request.method == 'POST' and 'nombre' in request.form and 'password' in request.form:
        username = request.form['nombre']
        password = request.form['password']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        cursor.execute('SELECT * FROM usuarios WHERE nombre = %s AND password = %s', (username, password,))
        
        account = cursor.fetchone()
        cursor.close()

        if account:
            session['login'] = True
            session['username'] = account['nombre']
            return redirect(url_for('home'))
        else:
            flash('Usuario o contraseña incorrecta', 'error')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    session.pop('_flashes', None)
    
    if request.method == 'POST' and 'nombre' in request.form and 'password' in request.form:
        username = request.form['nombre']
        password = request.form['password']
        
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        cursor.execute('SELECT * FROM usuarios WHERE nombre = %s', (username,))
        account = cursor.fetchone()
        
        if account:
            flash('La cuenta ya existe', 'error')
        elif not username or not password:
            flash('Por favor, rellene el formulario', 'error')
        else:
            cursor.execute('INSERT INTO usuarios (nombre, password) VALUES (%s, %s)', (username, password,))
            mysql.connection.commit()
            flash('Se ha registrado correctamente', 'success')
            return redirect(url_for('login'))
        
        cursor.close()
            
    return render_template('registro.html')

@app.route('/logout')
def logout():
    session.pop('login', None)
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)