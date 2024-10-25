import cv2
import numpy as np

# Initialisation du détecteur de visage
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Fonction pour détecter le visage avec le plus grand rectangle
def detect_face(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=6)
    if len(faces) == 0:
        return None, None, None, None, None
    best_face = max(faces, key=lambda rect: rect[2] * rect[3])
    x, y, w, h = best_face
    roi = frame[y:y+h, x:x+w]
    
    # Debugging output
    # print(f"Detected face at position: ({x}, {y}), width: {w}, height: {h}")
    
    return roi, x, y, w, h

# Fonction pour filtrer les visages avec une confiance inférieure à 8 %
def filter_by_confidence(w, h, frame_shape, threshold=7):
    confidence = (w * h) / (frame_shape[0] * frame_shape[1]) * 100  # Calculer la confiance en pourcentage
    return confidence >= threshold, confidence

# Fonction pour détecter le mouvement du visage
def detect_face_movement(previous_position, current_position, threshold=10):
    if previous_position is None:
        return False, 0  # Pas de mouvement si c'est la première frame
    prev_x, prev_y, _, _ = previous_position
    curr_x, curr_y, _, _ = current_position
    # Calculer le déplacement en fonction des coordonnées des centres
    movement = np.sqrt((curr_x - prev_x)**2 + (curr_y - prev_y)**2)
    return movement >= threshold, movement