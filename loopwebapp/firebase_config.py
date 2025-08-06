import firebase_admin
from firebase_admin import credentials, firestore
import pyrebase

# Inicializar firebase_admin
cred = credentials.Certificate('env/tu-archivo-firebase.json') 
firebase_admin.initialize_app(cred, {
    'storageBucket': 'loopapp-13b10.appspot.com'  
})

# Inicializar Pyrebase
firebase_config = {
    "apiKey": "AIzaSyD7cihT769KcAW2TI-6ojfpN_SV9yROkpY",
    "authDomain": "loopapp-13b10.firebaseapp.com",
    "databaseURL": "https://loopapp-13b10-default-rtdb.firebaseio.com",
    "projectId": "loopapp-13b10",
    "storageBucket": "loopapp-13b10.appspot.com",
    "messagingSenderId": "764577657193",
    "appId": "1:764577657193:web:c2daa1bdaf99c1ccdb0df8",
    "measurementId": "G-VQ4N4X0HE4"
}

firebase = pyrebase.initialize_app(firebase_config)
auth_pyrebase = firebase.auth()
db = firebase.database() 
firestore_db = firestore.client() 


