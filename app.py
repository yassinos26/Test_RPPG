from flask import Flask , render_template , session
from flask_socketio import SocketIO , emit
from face import detect_face , filter_by_confidence , detect_face_movement
from metrics import (calculate_activity, calculate_sleep, calculate_equilibrium,
                    calculate_metabolism, calculate_health, calculate_relaxation)
from vitals import (bandpass_filter, calculate_heart_rate, calculate_hrv, calculate_stress_level, calculate_blood_pressure,
                    calculate_spo2, verify_signal_strength, calculate_respiration_rate)
from PIL import Image
import io , base64 , cv2 , json , numpy as np

# Paramètres de capture
fs = 30  # Fréquence d'échantillonnage (frames par seconde)
lowcut = 0.85  # Fréquence de coupure basse (Hz)
highcut = 2.3  # Fréquence de coupure haute (Hz)
order = 4  # Ordre du filtre
frame_idx = []
stress_level_label = status = finished = ''
# Variables for face movement detection
previous_position = age = weight = height = None

# Limites des frames pour calculer différents signaux vitaux
max_frame_HR = 400
max_frame_SPO2 = 410
max_frame_HRV = 420
max_frame_pressions = 430
max_frame_respiration = 440
max_frame_total = 520  # Limite pour les frames totales

# Taille de la fenêtre glissante
window_size_HR = 100

app = Flask(__name__)
app.config['secret_key'] = 'Yassinos123456789'  # Nécessaire pour sécuriser les sessions

# Liste des origines autorisées
allowed_origins = ["http://127.0.0.1:5000", "https://yassinosmellouli.pythonanywhere.com"]
socketio = SocketIO(app, cors_allowed_origins=allowed_origins , manage_session=True)

# Face detection cascade
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Variables pour stocker les signaux RGB et RPPG 
signals = {"rppg_signal": [], "heart_rates": [], "spo2_rates": [], "hrv_rates": [], "respiration_rates": [],
        "systolic_rates": [], "diastolic_rates": [], "ppg_red_signal": [], "ppg_infra_signal": []}

# Variables moyennes et actuelles pour les signaux physiologiques
metrics = {"avg_bpm": 0, "bpm": 0, "avg_hrv": 0, "hrv": 0,
        "avg_spo2": 0, "spo2": 0, "avg_respiration": 0, "respiration": 0,
        "avg_diastolic": 0, "diastolic": 0, "avg_systolic": 0, "systolic": 0}

# Variables pour stocker les scores calculés par les métriques des signaux vitaux
scores = {"activity_score": 0, "sleep_score": 0, "equilibrium_score": 0,
        "metabolism_score": 0, "health_score": 0, "relaxation_score": 0}

# Fonction pour réinitialiser les signaux et les métriques si le nombre de frames dépasse une limite
def reset_signals_if_exceeds(frame_idx, signals, metrics):
    global finished
    signals["rppg_signal"].clear()
    signals["ppg_red_signal"].clear()
    signals["ppg_infra_signal"].clear()
    signals["heart_rates"].clear()
    signals["spo2_rates"].clear()
    signals["hrv_rates"].clear()
    signals["respiration_rates"].clear()
    signals["systolic_rates"].clear()
    signals["diastolic_rates"].clear()
    metrics["avg_bpm"] = 0
    metrics["avg_spo2"] = 0
    metrics["avg_hrv"] = 0
    metrics["avg_respiration"] = 0
    metrics["avg_systolic"] = 0
    metrics["avg_diastolic"] = 0
    frame_idx.clear()
    finished = ''
    
def reset_scores(scores):
    scores["activity_score"] = 0
    scores["sleep_score"] = 0
    scores["equilibrium_score"] = 0
    scores["metabolism_score"] = 0
    scores["health_score"] = 0
    scores["relaxation_score"] = 0

@app.route('/', methods=['GET'])
def index():
    return render_template('index0.html')

@app.route('/cam', methods=['GET'])
def cam():
    return render_template('index1.html')

@socketio.on('info')
def handle_info(information):
    global age, weight, height
    try:
        # Convertir la chaîne JSON reçue en dictionnaire
        info_dict = json.loads(information)
        
        # Stocker les valeurs dans la session
        session['age'] = int(info_dict.get('age', session.get('age'))) if info_dict.get('age') else session.get('age')
        session['weight'] = float(info_dict.get('weight', session.get('weight'))) if info_dict.get('weight') else session.get('weight')
        session['height'] = float(info_dict.get('height', session.get('height'))) if info_dict.get('height') else session.get('height')

    except ValueError:
        print('Error converting data to numeric values')
        
@socketio.on('reset')
def handle_image(reset_value):
    # reinstall all signals and frames
    reset_signals_if_exceeds(frame_idx, signals, metrics)
    # reinstall all scores
    reset_scores(scores)

@socketio.on('image')
def handle_image(data_image):
    global signals, metrics, frame_idx, stress_level_label, previous_position, status , finished 
    global age, weight, height

    try:
        # Récupérer les données stockées dans la session
        age = session.get('age', None)
        weight = session.get('weight', None)
        height = session.get('height', None)
        
        # Decode base64 image sent from the client
        b = io.BytesIO(base64.b64decode(data_image))
        pimg = Image.open(b)

        # Convert image to BGR (used by OpenCV)
        frame = cv2.cvtColor(np.array(pimg), cv2.COLOR_RGB2BGR)
        # Detect face in the frame
        face_roi, x, y, w, h = detect_face(frame)
        if face_roi is not None :
            is_confident, _ = filter_by_confidence(w, h, frame.shape)
            if is_confident:
                current_position = (x, y, w, h)
                is_moving, _ = detect_face_movement(previous_position, current_position)
                if is_moving:
                    status = 'Movement detected'
                else:
                    status = 'No movement'
                    frame_idx.append(len(frame_idx) + 1)  # Ajouter l'index de la frame
                    # print('les frames sont:', len(frame_idx))
                previous_position = current_position
                # Draw bounding box and status text
                cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
                cv2.putText(frame, f"Status: {status}", (x, y + h + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                roi_rgb = cv2.cvtColor(face_roi, cv2.COLOR_BGR2RGB)  # Convertir en RGB
                avg_color = np.mean(roi_rgb, axis=(0, 1))  # Moyenne des canaux R, G, B
                signals["rppg_signal"].append(avg_color[1])  # Utiliser le canal vert

                avg_red = np.mean(roi_rgb[:, :, 0])  # Moyenne du canal rouge
                avg_infra = 0.3 * avg_red + 0.59 * avg_color[1] + 0.11 * np.mean(roi_rgb[:, :, 2])  # Signal infrarouge
                signals["ppg_red_signal"].append(avg_red)  # Signal rouge
                signals["ppg_infra_signal"].append(avg_infra)  # Signal infrarouge

                if len(signals["rppg_signal"]) > 27 and len(signals["rppg_signal"]) < max_frame_total :
        
                    # Heart Rate traitement . Assuming this is within a loop that processes each frame or signal
                    filtered_signal = bandpass_filter(signals["rppg_signal"], lowcut, highcut, fs, order)
                    bpm, peak_intervals, peaks = calculate_heart_rate(filtered_signal, fs)
                    if bpm:
                        signals["heart_rates"].append(bpm)
                        # Check if we have enough heart rates to process
                        if len(signals["heart_rates"]) >= max_frame_HR:
                            start_index = max(0, len(signals["heart_rates"]) - window_size_HR)
                            heart_rate_window = signals["heart_rates"][start_index:len(signals["heart_rates"])]
                            metrics["avg_bpm"] = round(np.mean(heart_rate_window[-100:]), 2)
                            
                    if verify_signal_strength(signals["ppg_red_signal"]) and verify_signal_strength(signals["ppg_infra_signal"]):
                        spo2 = calculate_spo2(signals["ppg_red_signal"], signals["ppg_infra_signal"], fs)
                        signals["spo2_rates"].append(spo2)
                        metrics["avg_spo2"] = round(np.mean(signals["spo2_rates"]), 2) if len(signals["spo2_rates"]) >= max_frame_SPO2 else metrics["avg_spo2"]

                    if len(peaks) > 1:
                        _, hrv, _ = calculate_hrv(peaks)
                        signals["hrv_rates"].append(hrv)
                        metrics["avg_hrv"] = round(np.mean(signals["hrv_rates"]), 2) if len(signals["hrv_rates"]) >= max_frame_HRV else metrics["avg_hrv"]
                    
                    # Déterminer le niveau de stress
                    stress_level_label = calculate_stress_level(peak_intervals)
                    
                    respiration = calculate_respiration_rate(filtered_signal, fs)
                    signals["respiration_rates"].append(respiration)
                    metrics["avg_respiration"] = round(np.mean(signals["respiration_rates"]), 2) if len(signals["respiration_rates"]) >= max_frame_respiration else metrics["avg_respiration"]

                    systolic, diastolic = calculate_blood_pressure(peak_intervals)
                    if systolic and diastolic:
                        signals["systolic_rates"].append(systolic)
                        signals["diastolic_rates"].append(diastolic)
                        metrics["avg_systolic"] = round(np.mean(signals["systolic_rates"]), 2) if len(signals["systolic_rates"]) >= max_frame_pressions else metrics["avg_systolic"]
                        metrics["avg_diastolic"] = round(np.mean(signals["diastolic_rates"]), 2) if len(signals["diastolic_rates"]) >= max_frame_pressions else metrics["avg_diastolic"]
                
                if len(signals["rppg_signal"]) == max_frame_total:
                    # Calculer les scores à partir des métriques
                    scores["activity_score"] = calculate_activity(metrics["avg_bpm"], age)
                    scores["sleep_score"] = calculate_sleep(metrics["avg_hrv"], metrics["avg_respiration"])
                    scores["equilibrium_score"] = calculate_equilibrium(metrics["avg_hrv"], metrics["avg_systolic"], metrics["avg_diastolic"])
                    scores["metabolism_score"] = calculate_metabolism(weight, height, age)
                    scores["health_score"] = calculate_health(metrics["avg_spo2"], metrics["avg_bpm"], metrics["avg_systolic"])
                    scores["relaxation_score"] = calculate_relaxation(metrics["avg_hrv"], metrics["avg_respiration"])
                if len(frame_idx) == max_frame_total + 25:
                    finished = 'True'
                    frame_idx = []
            else:
                status = 'Low confidence, no detection'
        else:
            status = 'No face detected'
            
        
        # Encode the processed image as a JPEG and convert to base64
        _, img_encoded = cv2.imencode('.jpg', frame)
        stringData = base64.b64encode(img_encoded).decode('utf-8')
        b64_src = f'data:image/jpeg;base64,{stringData}'
                
        # Emit the processed image to the client
        emit('image_back', b64_src)
        
        # Emit the metrics results to the client
        emit('metrics_back', {
            'metrics': {
                'bpm': metrics["avg_bpm"],
                'hrv': metrics["avg_hrv"],
                'spo2': metrics["avg_spo2"],
                'respiration': metrics["avg_respiration"],
                'diastolic': metrics["avg_diastolic"],
                'systolic': metrics["avg_systolic"],
                'stress_level': stress_level_label
            },
            'status': status
        })
        
        # Emit the scores results to the client
        emit('scores_back', {
            'scores': {
                'activity_score': scores["activity_score"],
                'sleep_score': scores["sleep_score"],
                'equilibrium_score': scores["equilibrium_score"],
                'metabolism_score': scores["metabolism_score"],
                'health_score': scores["health_score"],
                'relaxation_score': scores["relaxation_score"]
            }
        })
        
        # Emit the finish process to the client
        if finished == 'True':
            emit('close_back', finished)
            finished = ''
        
    except Exception as e:
        print(f"Error processing image: {e}")
        emit('response_back', "Error processing image")
        emit('resultat_back', "Error send results of processing")
        emit('scores_back', "Error send scores of processing")
        emit('close_back', "Error of close")
        
if __name__ == '__main__':
    socketio.run(app, host='127.0.0.1', port=5000 , debug=True)