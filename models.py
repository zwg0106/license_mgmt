from exts import db
from datetime import datetime

class LicenseServerModel(db.Model):
    __tablename__ = 'license_server'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    customer_name = db.Column(db.String(50), nullable=False)
    owner = db.Column(db.String(50), nullable=False)
    product = db.Column(db.String(50), nullable=False)
    maxusercount = db.Column(db.Integer, nullable=False)
    availusercount = db.Column(db.Integer, nullable=False)


class LicenseClientModel(db.Model):
    __tablename__ = 'license_client'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cardtype = db.Column(db.String(20), nullable=False)
    sn = db.Column(db.String(12), nullable=False)
    mac_addr = db.Column(db.String(17), nullable=False)
    status = db.Column(db.String(10), nullable=False)
    issued_time = db.Column(db.DateTime, default=datetime.now)
    expired_time = db.Column(db.DateTime, default=datetime.now)
    filename = db.Column(db.String(50), nullable=False)
    filesize = db.Column(db.String(100), nullable=False)
    qrfile = db.Column(db.String(50), nullable=False)
    server_id = db.Column(db.Integer, db.ForeignKey('license_server.id'))
    server = db.relationship('LicenseServerModel', backref=db.backref('clients'))
