# -*- coding: utf-8 -*-
import qi
import subprocess
import speech_recognition as sr
import json
import requests
import time
import threading
import random

class PepperElderAssistant:
    def __init__(self, session):
        self.session = session
        self.tts = self.session.service("ALTextToSpeech")
        self.memory = self.session.service("ALMemory")
        self.face_detection = self.session.service("ALFaceDetection")
        self.motion = self.session.service("ALMotion")

        self.recognizer = sr.Recognizer()

        # Database degli utenti: Nome -> Condizioni personali
        self.user_profiles = {
            "Mario rossi": {"conditions": ["diabete"], "greeting": "Ciao Mario! sono contento di rivederti."},
            "Anna Verdi": {"conditions": ["ipertensione"], "greeting": "Ciao Anna! Attenta al sale nei tuoi pasti."},
            "Francesco": {"conditions": ["ipertensione"], "greeting": "ciao francesco"},
            "Samuel": {"conditions": ["diabete"], "greeting": "ciao Samuel! sono contento di rivederti"}
        }
        self.first_interaction = True  # Flag per gestire la prima interazione
        self.current_condition = "generico"  # Condizione di default per quando l'utente non è riconosciuto

    def perform_speech_recognition(self):
        """Riconosce il testo dalla registrazione audio e ripete la domanda se non capisce."""
        with sr.Microphone() as source:
            print("Posiziona il microfono. Inizia a parlare.")
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            try:
                audio_data = self.recognizer.listen(source, timeout=5)
                transcription = self.recognizer.recognize_google(audio_data, language="it-IT")
                print("Testo riconosciuto:", transcription)
                return transcription
            except sr.WaitTimeoutError:
                print("Nessun audio rilevato, prova a parlare più forte.")
            except sr.UnknownValueError:
                print("Non sono riuscito a capire l'audio, per favore ripeti.")
            except sr.RequestError as e:
                print("Errore con il servizio di riconoscimento:", e)
            return None

    def respond_with_text(self, text):
        """Far parlare il robot usando il servizio ALTextToSpeech."""
        print("Il robot dice:", text)
        self.tts.say(text)

    def chat_with_gpt(self, user_input, user_name, user_condition):
        """Interagisce con ChatGPT per risposte naturali e per dare """
        try:
            openai_api_key = ""
            url = 'https://api.openai.com/v1/chat/completions'
            headers = {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer {}'.format(openai_api_key)
            }

            system_message = (
                "Sei Pepper, un robot gentile e rassicurante che assiste anziani. Cerca di non dare risposte troppo lunghe per far sì che la conversazione sia il più naturale possibile. "
                "Il mio utente, {}, soffre di {}. "
                "Se l'utente descrive un cibo, fai attenzione alla sua condizione e fornisci un consiglio dietetico. "
                "Se non è sano per lui, informalo con tatto e suggerisci alternative migliori, altrimenti fai i complimenti all'utente sulla scelta del cibo e incoraggialo"
                "Evita risposte troppo lunghe per garantire una conversazione naturale"
                "Ricordati ciò che dice l'utente durante la conversazione"
                "Se dimentichi un'informazione importante, chiedi conferma all'utente"
                "Adatta le tue risposte in base alla condizione dell'utente, assicurandoti che ogni consiglio sia appropriato".format(user_name, user_condition)
            )

            data = {
                "model": "gpt-4",
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_input}
                ],
                "max_tokens": 150,
                "temperature": 0.7
            }
            response = requests.post(url, headers=headers, data=json.dumps(data))
            response_json = response.json()

            if response.status_code == 200:
                response_content = response_json['choices'][0]['message']['content']
                print("Risposta di ChatGPT:", response_content)

                # Lista di animazioni da cui scegliere casualmente
                animations = [
                    "animations/Stand/Gestures/Explain_2",
                    "animations/Stand/Gestures/HeSays_1",
                    "animations/Stand/Gestures/Enthusiastic_3",
                    "animations/Stand/Gestures/Explain_8"
                ]
                selected_animation = random.choice(animations)
                self.play_animation_with_speech(selected_animation, response_content)
            else:
                print("Errore nell'API di OpenAI:", response_json)
                return "Scusa, c'è stato un problema con la mia risposta."
        except Exception as e:
            print("Errore nella comunicazione con ChatGPT:", e)
            return "Scusa, ho avuto un problema tecnico."

    def register_user(self):
        """Registra un nuovo utente associando un volto a un nome."""
        self.respond_with_text("Per favore, dimmi il tuo nome completo per registrarti.")
        user_name = self.perform_speech_recognition()

        if not user_name:
            self.respond_with_text("Non ho capito il tuo nome. Riprova, per favore.")
            return

        self.respond_with_text("Grazie, {}. Ora scansionerò il tuo volto. Per favore, guarda verso di me.".format(user_name))
        self.face_detection.subscribe("FaceRegistration")
        time.sleep(2)  # Attendi per acquisire il volto
        try:
            self.face_detection.learnFace(user_name)  # Registra il volto con il nome
            self.face_detection.unsubscribe("FaceRegistration")
            self.user_profiles[user_name] = {"conditions": [], "greeting": "Ciao {}! Sono felice di vederti di nuovo.".format(user_name)}
            self.respond_with_text("Registrazione completata. Piacere di conoscerti, {}!".format(user_name))
        except Exception as e:
            self.face_detection.unsubscribe("FaceRegistration")
            print("Errore durante la registrazione del volto:", e)
            self.respond_with_text("Non sono riuscito a registrare il tuo volto. Proviamo di nuovo più tardi.")

    def perform_face_recognition(self):
        """Riconosce il volto dell'utente e restituisce il nome."""
        print("Avvio del riconoscimento facciale...")
        self.face_detection.subscribe("Test_Face")
        time.sleep(2)  # Attendi per la scansione del volto
        face_data = self.memory.getData("FaceDetected")  # Recupera i dati dal servizio ALMemory

        self.face_detection.unsubscribe("Test_Face")

        if face_data and isinstance(face_data, list) and len(face_data) > 0:
            try:
                face_info = face_data[1][0][1]  # Estrarre il nome associato al volto
                recognized_name = face_info[2] if len(face_info) > 2 else None
                if recognized_name:
                    print("Utente riconosciuto:", recognized_name)
                    return recognized_name
                else:
                    print("Nessun nome associato al volto.")
                    return None
            except IndexError:
                print("Struttura dei dati FaceDetected non conforme.")
                return None
        else:
            print("Nessun volto riconosciuto.")
            return None

    def provide_personalized_advice(self, user_name):
        """Fornisce consigli personalizzati in base al profilo utente."""
        profile = self.user_profiles.get(user_name)
        if profile:
            greeting = profile["greeting"]
            self.respond_with_text(greeting)
            return profile["conditions"][0] if profile["conditions"] else "generico"
        else:
            self.respond_with_text("Ciao! Non ho informazioni sul tuo profilo, ma sono qui per aiutarti.")
            return "generico"


    def move_arms_and_head(self):
        """Esegui movimenti naturali durante il parlato, come braccia e testa."""
        print("Muovendo le braccia e la testa durante il parlato...")

        # Posizioni random delle braccia
        shoulder_pitch = random.uniform(1.5, 1.5)  # Movimento delle spalle (su o giù)
        elbow_yaw = random.uniform(-1.5, 1.0)     # Angolo del gomito (a sinistra o destra)
        wrist_yaw = random.uniform(-0.5, 0.5)     # Angolo del polso

        # Movimento della testa
        head_yaw = random.uniform(-0.2, 0.2)      # Movimento della testa a sinistra o destra
        head_pitch = random.uniform(-0.1, 0.2)    # Movimento della testa su o giù

        # Movimenti random
        self.motion.setAngles("RShoulderPitch", shoulder_pitch, 0.2)
        self.motion.setAngles("RElbowYaw", elbow_yaw, 0.2)
        self.motion.setAngles("RWristYaw", wrist_yaw, 0.2)
        self.motion.setAngles("HeadYaw", head_yaw, 0.1)
        self.motion.setAngles("HeadPitch", head_pitch, 0.1)

        time.sleep(2)  # Muovi le braccia e la testa per 2 secondi

        # Riporta le braccia e la testa alla posizione neutra
        self.motion.setAngles("RShoulderPitch", 1.5, 0.2)
        self.motion.setAngles("RElbowYaw", 0.0, 0.2)
        self.motion.setAngles("RWristYaw", 0.0, 0.2)
        self.motion.setAngles("HeadYaw", 0.0, 0.1)
        self.motion.setAngles("HeadPitch", 0.0, 0.1)

    def play_animation_with_speech(self, animation_name, text):
        """Esegui un'animazione mentre Pepper parla."""
        def speak():
            self.respond_with_text(text)  # Funzione di parlato del robot

        def animate():
            try:
                animation_player = self.session.service("ALAnimationPlayer")
                animation_player.run(animation_name)
                print("Eseguita l'animazione: {}".format(animation_name))
            except Exception as e:
                print("Errore durante l'esecuzione dell'animazione {}: {}".format(animation_name, e))

        # Avvia l'animazione e il parlato in parallelo
        animation_thread = threading.Thread(target=animate)
        speech_thread = threading.Thread(target=speak)

        animation_thread.start()
        speech_thread.start()

        # Aspetta che entrambi i thread finiscano
        animation_thread.join()
        speech_thread.join()


    def assist_elders_during_meal(self):
        """Gestisce il processo completo di assistenza."""
        self.play_animation_with_speech("animations/Stand/Gestures/Hey_4", "Ciao! Sono Pepper, il tuo assistente personale. Sono qui per aiutarti durante i pasti.")
        self.play_animation_with_speech("animations/Stand/Gestures/Explain_1", "Inizio il riconoscimento, per favore guarda verso il mio volto")
        user_name = self.perform_face_recognition()

        if user_name:
            self.current_condition = self.provide_personalized_advice(user_name)
        else:
            self.play_animation_with_speech("animations/Stand/Gestures/Explain_1","non sono riuscito a riconoscerti. Vuoi essere registrato?. in questo modo potrò darti dei consigli personalizzati")
            self.respond_with_text("rispondimi con si se vuoi essere registrato mentre rispondimi con no se non vuoi essere registrato")


    # Chiedi se registrarsi o riconoscersi in un loop finché non ottieni una risposta valida
            while True:
                user_response = self.perform_speech_recognition()

                if user_response:
                    user_response = user_response.lower()
                    if "s" in user_response:
                        self.register_user()
                        break
                    elif "no" in user_response:
                        self.respond_with_text("va bene, continuamo senza registrazione.")
                        self.current_condition = "generico"
                        break
                    else:
                        self.respond_with_text("Scusami non ho capito, puoi ripetere con si o no?") 


        #dopo aver gestito il riconoscimento e la registrazione, inzia la conversazione con l'utente
        if self.first_interaction:
            self.play_animation_with_speech("animations/Stand/Gestures/Explain_1","Stai mangiando oppure hai finito?")
            user_input = self.perform_speech_recognition()
            if not user_input:
                self.play_animation_with_speech("animations/Stand/BodyTalk/Thinking/ThinkingLoop_2","Non ho capito puoi ripetere?")
                self.assist_elders_during_meal()
                return
                
            if "sto mangiando" in user_input.lower() or "ho finito" in user_input.lower():
                self.respond_with_text("Cosa hai mangiato?")
                food_input = self.perform_speech_recognition()

                if food_input:
                    response = self.chat_with_gpt(food_input, "utente", self.current_condition)
                    self.respond_with_text("Possiamo conversare di qualsiasi cosa tu voglia. Quando vuoi terminare la conversazione, ti basta dire stop")
            else:

                response = self.chat_with_gpt(user_input, "utente", self.current_condition)
      

        # Dopo la prima domanda, continua ad ascoltare e rispondere
        while True:
            user_input = self.perform_speech_recognition()

            if not user_input:
                self.respond_with_text("Non ho capito. Puoi ripetere?")
                continue

            if "stop" in user_input.lower():
                if hasattr(self, "recognized_user_name") and self.recognized_user_name:
                    self.respond_with_text("Arrivederci {}! Buona giornata!".format(self.recognized_user_name))
                else:
                    self.respond_with_text("Arrivederci! Buona giornata!")
                break


            if "sto mangiando" in user_input.lower() or "ho finito" in user_input.lower():
                self.respond_with_text("Cosa stai mangiando?")
                food_input = self.perform_speech_recognition()

                if food_input:
                    response = self.chat_with_gpt(food_input, "utente", self.current_condition)
                    self.respond_with_text("Possiamo conversare di qualsiasi cosa tu voglia. Quando vuoi terminare la conversazione, ti basta dire stop")
            else:

                response = self.chat_with_gpt(user_input, "utente", self.current_condition)

if __name__ == "__main__":
    try:
        app = qi.Application()
        session = app.session
        session.connect("tcp://192.168.32.201:9559")  # Modifica l'IP del robot se necessario
        pepper_assistant = PepperElderAssistant(session)
        pepper_assistant.assist_elders_during_meal()
    except KeyboardInterrupt:
        print("Interruzione del programma.")