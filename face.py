import cv2
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
    return roi, x, y, w, h
# Fonction pour filtrer les visages avec une confiance inférieure à 8 %
def filter_by_confidence(w, h, frame_shape, threshold=7):
    confidence = (w * h) / (frame_shape[0] * frame_shape[1]) * 100  # Calculer la confiance en pourcentage
    return confidence >= threshold, confidence