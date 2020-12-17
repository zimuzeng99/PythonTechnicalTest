from flask import request, jsonify, abort, g, Flask
from flask_sqlalchemy import SQLAlchemy
import requests
import simplejson as json
import decimal
import datetime
from passlib.apps import custom_app_context as pwd_context
from flask_httpauth import HTTPBasicAuth

auth = HTTPBasicAuth()

db = SQLAlchemy()

app = Flask(__name__)

app.config['SECRET_KEY'] = 'secret-key-goes-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'

class User(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    username = db.Column(db.String(32))
    password_hash = db.Column(db.String(128))
    
    def hash_password(self, password):
        self.password_hash = pwd_context.encrypt(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)
    
class Bond(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    isin = db.Column(db.String(12))
    size = db.Column(db.Numeric(10,2))
    currency = db.Column(db.String(3))
    maturity = db.Column(db.Date())
    lei = db.Column(db.String(20))
    legal_name = db.Column(db.String(100))
    added_by = db.Column(db.Integer, db.ForeignKey('user.id'))

db.init_app(app)

@app.route('/signup', methods=['POST'])
def signup():
    username = request.json.get('username')
    password = request.json.get('password')
    if username is None or password is None:
        abort(400) # missing arguments
    if User.query.filter_by(username = username).first() is not None:
        abort(400) # existing user
    user = User(username = username)
    user.hash_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({ 'username': user.username }), 200

@auth.verify_password
def verify_password(username, password):
    user = User.query.filter_by(username = username).first()
    if not user or not user.verify_password(password):
        return False
    g.user = user
    return True

@app.route('/bonds', methods=['POST'])
@auth.login_required
def add_bond():
    # Check if the same user has already added the same bond in the past
    existing_bond = Bond.query.filter_by(isin = request.json['isin'], added_by=g.user.id).first()
    if existing_bond:
        return jsonify({'success': False, 'error': 'This bond has already been added in the past'}), 400
    
    lei_api_url = "https://leilookup.gleif.org/api/v2/leirecords?lei=" + request.json['lei']
    lei_response = requests.get(lei_api_url)
    lei_response_json = json.loads(lei_response.text)
    legal_name = lei_response_json[0]['Entity']['LegalName']['$'].replace(" ", "") # remove whitespace from legal name
    
    new_bond = Bond(isin=request.json['isin'], 
                    size=decimal.Decimal(request.json['size']), 
                    currency=request.json['currency'], 
                    maturity=datetime.date.fromisoformat(request.json['maturity']), 
                    lei=request.json['lei'],
                    legal_name=legal_name,
                    added_by=g.user.id)
    
    db.session.add(new_bond)
    db.session.commit()
    return jsonify({'success':True}), 200

@app.route('/bonds', methods=['GET'])
@auth.login_required
def get_bonds():
    legal_name = request.args.get('legal_name')
    if legal_name:
        bonds = Bond.query.filter_by(added_by=g.user.id, legal_name=legal_name).all()
    else:
        bonds = Bond.query.filter_by(added_by=g.user.id).all()
        
    json_serializable_bonds = []
    for bond in bonds:
        serializable_bond = {
            "isin": bond.isin,
            "size": bond.size,
            "currency": bond.currency,
            "maturity": bond.maturity.isoformat(),
            "lei": bond.lei,
            "legal_name": bond.legal_name
        }
        
        json_serializable_bonds.append(serializable_bond)
        
    return json.dumps(json_serializable_bonds), 200
        
        


    
    