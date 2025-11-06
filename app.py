from flask import Flask
from flask import render_template
from flask_mysqldb import MySQL

app = Flask(__name__)
app.secret_key = 'unirproyecto'
app.config['MYSQL_HOST'] = '45.195.229.16'
app.config['MYSQL_USER'] = 'adminremote'
app.config['MYSQL_PASSWORD'] = 'unir'
app.config['MYSQL_DB'] = 'unir'
mysql = MySQL(app)

@app.route('/')
def home():
 #   if 'login' in session:
  #      return redirect('/login)
    cursor  = mysql.connection.cursor()
    cursor.execute('SELECT * FROM usuarios')
    results = cursor.fetchall()
    cursor.close()

    return render_template('index.html', data=results)

@app.route('/login', methods=['GET', 'POST'])
def login():
    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True)


