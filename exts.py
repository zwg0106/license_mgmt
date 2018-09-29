import pymysql
from flask_sqlalchemy import SQLAlchemy

pymysql.install_as_MySQLdb()

db = SQLAlchemy()