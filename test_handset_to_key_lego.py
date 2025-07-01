import subprocess
import keyboard
import time
import sys
import threading


ip="70:B9:50:59:54:95" #vôtre ip/id de télécommande / your handset ip/id

class HandsetController:
    def __init__(self):
        # États des boutons, True = appuyé, False = relâché
        self.left_up = False
        self.left_down = False
        self.left_center = False
        self.right_up = False
        self.right_down = False
        self.right_center = False
        self.center_button = False
        
        # Pour mémoriser l'état actuel des touches (pressées ou non)
        self._key_states = {
            "left": False,
            "right": False,
            "a": False,
            "up": False,
            "down": False,
            "b": False,
            "space": False,
        }
        
        self._last_repeat = {}
    
    def update_state(self,ip, response):
        if f"{ip} : handset action = + right button down" in response:
            self.right_up = True
            self.right_down = False
            self.right_center = False
        elif f"{ip} : handset action = - right button down" in response:
            self.right_down = True
            self.right_up = False
            self.right_center = False
        elif f"{ip} : handset action = center right button down" in response:
            self.right_center = True
            self.right_up = False
            self.right_down = False
        elif f"{ip} : handset action = all right button up" in response:
            self.right_up = False
            self.right_down = False
            self.right_center = False
        elif f"{ip} : handset action = + left button down" in response:
            self.left_up = True
            self.left_down = False
            self.left_center = False
        elif f"{ip} : handset action = - left button down" in response:
            self.left_down = True
            self.left_up = False
            self.left_center = False
        elif f"{ip} : handset action = center left button down" in response:
            self.left_center = True
            self.left_up = False
            self.left_down = False
        elif f"{ip} : handset action = all left button up" in response:
            self.left_up = False
            self.left_down = False
            self.left_center = False
        elif f"{ip} : handset action = center button down" in response:
            self.center_button = True
        elif f"{ip} : handset action = center button up" in response:
            self.center_button = False
        print(f"Changement d'état détecté !")

    def apply_key_events(self):
        mapping = {
            "left": self.right_up,
            "right": self.right_down,
            "a": self.right_center,
            "up": self.left_up,
            "down": self.left_down,
            "b": self.left_center,
            "space": self.center_button,
        }

        for key, should_press in mapping.items():
            is_pressed = self._key_states[key]

            if should_press and not is_pressed:
                keyboard.press(key)
                self._key_states[key] = True
            elif not should_press and is_pressed:
                keyboard.release(key)
                self._key_states[key] = False
        

security=False

def main():
    global ip, security
    # Lance l'application existante et garde le stdin/stdout ouverts
    process = subprocess.Popen(
        ['test_command_lego_powerup.exe'],  # ou ['python3', ...] selon ton système
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,   # pour travailler avec des str au lieu de bytes
        encoding='utf-8',
        bufsize=1    # line buffered
    )

    try:
        time.sleep(3)
        # Envoie une commande
        cmd = f"start_connection:{ip}\n"
        print(f"Envoi de la commande : {cmd.strip()}")
        process.stdin.write(cmd)
        process.stdin.flush()
        
        time.sleep(1)
        # Envoie une commande
        cmd = f"command_hub_color:{ip};port:34;code:03\n"
        print(f"Envoi de la commande : {cmd.strip()}")
        process.stdin.write(cmd)
        process.stdin.flush()
        
        time.sleep(1)
        # Envoie une commande
        cmd = f"command_start_listen_handset:{ip}\n"
        print(f"Envoi de la commande : {cmd.strip()}")
        process.stdin.write(cmd)
        process.stdin.flush()

        controller = HandsetController()

        def repeat_keys_loop(controller):
            global security
            while security==False:
                controller.apply_key_events()
                time.sleep(0.05)
    
        threading.Thread(target=repeat_keys_loop, args=(controller,), daemon=True).start()

        while True:
            # Attend une réponse
            response = process.stdout.readline()
            
            if not response:
                break

            response = response.strip()
            print(f"Réponse reçue : {response}")

            controller.update_state(ip, response)
            

    except Exception as e:
        print(f"Erreur : {e}")

    finally:
        security==True
        print("Fermeture du processus")
        cmd = f"Switch_Off_Hub:{ip}\n"
        process.stdin.write(cmd)
        process.stdin.flush()
        time.sleep(1)
        process.terminate()
        
#release
main()
