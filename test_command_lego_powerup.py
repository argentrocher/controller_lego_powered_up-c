import asyncio
import sys
import os
from bleak import BleakScanner, BleakClient
from concurrent.futures import ThreadPoolExecutor

CHAR_UUID = "00001624-1212-efde-1623-785feabcd123"


# Chemin dossier app (exe ou py)
if getattr(sys, 'frozen', False):
    app_path = os.path.dirname(sys.executable)
else:
    app_path = os.path.dirname(__file__)

# Chemin du fichier (dans le même dossier que le script principal)
uuid_file = os.path.join(app_path, "char_uuid_lego_controller.txt")

# S'il existe, on lit le texte du fichier et on le remplace
if os.path.isfile(uuid_file):
    try:
        with open(uuid_file, "r", encoding="utf-8") as f:
            new_uuid = f.readline().strip()
            # Petite vérif simple que ça ressemble à un UUID
            if len(new_uuid) >= 35:
                CHAR_UUID = new_uuid
                print(f"✅ CHAR_UUID remplacé par valeur du fichier char_uuid_lego_controller.txt: {CHAR_UUID}")
            else:
                print("⚠️ Le fichier char_uuid_lego_controller.txt ne contient pas un UUID valide")
    except Exception as e:
        print(f"Erreur lecture char_uuid_lego_controller.txt : {e}")


test_byte_info="""
exemple de commande réelement exécuté lors de la création de l'application en 2025:\n
les identifiants sont uniques et ne fonctionne que si vous avez le bon hub, pour les récupérers, allume ton ou tes hubs et exécute "connection_list"\n
\n
#start_connexion:00:16:53:AD:00:73 (hub move)  ---> changer les ids pour vos hub\n
#command_output:70:B9:50:59:54:95;08 00 81 34 11 51 00 03 (changer la couleur de la led pour la télécommande port 34 et non 32)\n
#command_output:90:84:2B:CC:64:F5;08 00 81 00 11 51 01 9C (moteur pas a pas (pas train))\n
#command_output:90:84:2B:CC:64:F5;0A 00 81 [PORT] 11 07 [VITESSE] [MAXPOWER] [USEPROFILE] (0A 00 81 00 11 07 32 64 00) (moteur pas à pas avec gestion de puissance maximum le useprofile=00)\n
#command_output:90:84:2B:CC:64:F5;08 00 81 [port] 11 51 00 [puissance] (ici train fonctionne car pas de 01 control de vitesse (led aussi))\n
#command_output:90:84:2B:CC:64:F5;08 00 81 32 11 51 00 [couleur] (changer la couleur de la led par code le 32 corespond au port peut être changer pour des leds mais vu qu'elle ne sont pas rgb inutile)\n

#command_output:90:84:2B:CC:64:F5;0E 00 81 00 11 0D 68 01 00 00 32 64 7F 00 (aller à une position global avec un moteur angulaire) 0E 00 81 [port] 11 0D [position] [position] [position] [position] [vitesse] [puissancemax] [frein(7F) ou NULL (00)] [profile]\n
#command_output:90:84:2B:CC:64:F5;0E 00 81 00 11 0B 68 01 00 00 32 64 7F 01 (ajouter à la position actuelle un angle avec une vitesse) 0E 00 81 [port] 11 0B [position] [position] [position] [position] [vitesse] [puissancemax] [frein] [profile]\n
#command_output:90:84:2B:CC:64:F5;0C 00 81 00 11 09 E8 03 32 64 7F 00 (faire tourné le moteur pendant un temps donné) 0C 00 81 [port] 11 09 [durée] [durée] [vitesse] [puissancemax] [frein] [profile]\n
#command_output:90:84:2B:CC:64:F5;0A 00 41 00 02 00 00 00 01 00 (commande de configuration des ports Type de message : Format d’entrée simple) 0A 00 41 [port] [mode 02=capteuroumoteur] [time] [time] [time] [time] [notification(00 ou 01)] (permet d'avoir la position d'un moteur pas à pas)\n

#command_output:90:84:2B:CC:64:F5;0A 00 41 01 01 01 00 00 00 01 (messure la distance de changement entre le capteur et l'objet renvoie 050045010[distance]) changé le dernière octet à 00 pour désactiver les notifs) 0A 00 41 [port] [tipe] 01 00 00 00 [notificationON/OFF] (tipe varie 00=couleur 01=distance 02=passage 03=lumière réfléchie, 04=lumière ambiante, 06=couleurRAW)\n

#command_output:70:B9:50:59:54:95;05 00 21 28 01 (commande d'info sur les port) 05 00 21 [port] [tipe(00,01parfois02pourvirtuel)]\n

#command_output:90:84:2B:CC:64:F5;04 00 02 01 commande d'éteindre (04 00 02 02 pour déconnecter)\n

#command_output:90:84:2B:69:52:82;0A 00 41 [port] 00 01 00 00 00 01 (info port pour technic hub 61 position 62 rotation, 63 accéléromètre)\n

fin des tests\n
"""

class LegoController:
    def __init__(self):
        self.clients = {}  # id -> BleakClient
        self.loop = asyncio.get_event_loop()
        self.executor = ThreadPoolExecutor(max_workers=10)
        
        #savoir si on doit récupérer la position absolu du moteur
        self.get_motor_absolute_position = []
        #savoir si on doit controller la télécommande
        self.get_msg_handset = []

    def make_notification_handler(self, device_id):
        def handler(sender, data):
            hex_msg = data.hex().upper()
            print(f"📨 Réponse de {device_id}: {hex_msg}")
            sys.stdout.flush()

            try:
                # Vérifier qu'on a bien configuré au moins un suivi pour la position du moteur à tachymètre
                if self.get_motor_absolute_position:
                    # Vérifier que le message commence par 08 00 45
                    if hex_msg.startswith('080045'):
                        # Port : c’est le 4ème octet (index 3)
                        port_byte = data[3]
                        port_char = chr(65 + port_byte)  # 0 -> A, 1 -> B, etc.

                        # Position absolue : les 3 octets suivants (index 4,5,6)
                        # Comme c’est little endian, on fait :
                        pos_bytes = data[4:7]
                        position = int.from_bytes(pos_bytes, byteorder='little', signed=True)

                        # Chercher si dans get_motor_absolute_position on a (True, device_id, port_char)
                        for active, target_device_id, target_port in self.get_motor_absolute_position:
                            if active and target_device_id == device_id and target_port == port_char:
                                print(f"✅ Réponse de {device_id} / Port {target_port} : position motor = {position}°")
                                break
                            
                # --- Partie télécommande ---
                if device_id in self.get_msg_handset:
                    # Dictionnaire pour mapper les messages connus
                    remote_msgs = {
                    '0500080201': "center button down",
                    '0500080200': "center button up",
                    '0500450000': "all left button up",
                    '050045007F': "center left button down",
                    '0500450001': "+ left button down",
                    '05004500FF': "- left button down",
                    '0500450100': "all right button up",
                    '050045017F': "center right button down",
                    '0500450101': "+ right button down",
                    '05004501FF': "- right button down",
                    }

                    # On prend les 5 premiers octets du message pour matcher
                    msg_key = hex_msg[:10]

                    if msg_key in remote_msgs:
                        action = remote_msgs[msg_key]
                        print(f"🎮 Réponse de {device_id} : handset action = {action}")
                        
            except Exception as e:
                print(f"Erreur décodage message : {e}")
                sys.stdout.flush()
        return handler

    async def scan(self):
        devices = await BleakScanner.discover(timeout=5.0)
        hubs = []
        for d in devices:
            if d.name :#and ("hub" in d.name or "Hub" in d.name or "LEGO" in d.name or "lego" in d.name or "city" in d.name or "Move Hub" in d.name): #désactiver car les noms des hubs peuvent être changer par l'utilisateur
                hubs.append((d.address, d.name))
        return hubs

    async def connect(self, device_id):
        if device_id in self.clients:
            return f"Déjà connecté à {device_id}"
        client = BleakClient(device_id)
        try:
            await client.connect()
            if client.is_connected:
                await client.start_notify(CHAR_UUID, self.make_notification_handler(device_id))
                self.clients[device_id] = client
                return f"Connecté à {device_id}"
            else:
                return f"Échec de la connexion à {device_id}"
        except Exception as e:
            return f"Erreur connexion {device_id} : {e}"

    async def disconnect(self, device_id):
        client = self.clients.get(device_id)
        if not client:
            return f"Pas connecté à {device_id}"
        try:
            await client.stop_notify(CHAR_UUID)
            await client.disconnect()
            del self.clients[device_id]
            return f"Déconnecté de {device_id}"
        except Exception as e:
            return f"Erreur déconnexion {device_id} : {e}"

    async def disconnect_all(self):
        results = []
        for device_id in list(self.clients.keys()):
            res = await self.disconnect(device_id)
            results.append(res)
        return "\n".join(results)

    async def send_command(self, device_id, data_bytes):
        client = self.clients.get(device_id)
        if not client or not client.is_connected:
            if client and not client.is_connected:
                del self.clients[device_id]
            return f"Pas connecté à {device_id}"
        try:
            await client.write_gatt_char(CHAR_UUID, data_bytes)
            
            # Vérifier si c’est une commande qui doit entraîner la suppression du client
            commands_to_remove = [
            bytes([0x03, 0x00, 0x02, 0x01]),
            bytes([0x04, 0x00, 0x02, 0x01]),
            bytes([0x03, 0x00, 0x02, 0x02]),
            bytes([0x04, 0x00, 0x02, 0x02]),
            ]
            if data_bytes in commands_to_remove:
                del self.clients[device_id]
            
            return f"Commande envoyée à {device_id}"
        except Exception as e:
            return f"Erreur envoi commande à {device_id} : {e}"

    def run_async(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

async def parse_command(controller, line):
    line = line.strip()
    if line == "info" or line == "info()" or line == "help" or line == "help()":
        text_info="""
        info du controller LEGO Powered up (c):\n
        cette application n'est aucunement liée au groupe lego d'une quelquonque façon et à été créer grâce à la documentation de lego\n
        créer par argentropcher assigné au compte google argentropcher tout droit réserver (modification et vente de cette application est strictement interdite)\n
        Les commandes de cette application:\n
        "connexion_list" et "connection_list" liste les hubs lego allumés et permet une récupération de leur id unique (ex: '00:16:53:AD:00:73')\n
        "start_connexion:'id'" et "start_connection:'id'" permet de connecter les hubs à l'ordinateur\n
        "close_connexion:'id'" et "close_connection:'id'" déconnecte les hubs au niveau du bluetooth de l'ordinateur\n
        Ces commandes utilisent du BLE sur l'UUID de LEGO actuel, si l'UUID change, créer un fichier char_uuid_lego_controller.txt avec la nouvelle UUID\n
        UUID du programme = 00001624-1212-efde-1623-785feabcd123\n
        commande de controle des hubs une fois connecté :\n
        Switch_Off_Hub:'id' permet d'étiendre le hub proprement
        command_hub_color:'id';port:'port';code:'code' | 'port' est la valeur du port de la led, actuellement 32 ou 34, 'code' est un nombre entre 0 et 10 corespondant à une couleur\n
        command_power:'id';port:'port';speed:'speed' | 'port' est une lettre A B C ou D, 'speed' est un nombre entre -100 et 100, permet de faire tourné un moteur ou d'allumé des leds\n
        command_power_motor_tacho:'id';port:'port';speed:'speed' | identique à command_power mais uniquement pour des moteurs à tachymètre (pas à pas)\n
        command_speed_control_motor_tacho:'id';port:'port';speed:'speed';maxpower:'maxpower' | 'port' et 'speed' sont identiques, 'maxpower' permet de définir une puissance maximum du moteur\n
        tout en gardant une vitesse voulu, maxpower doit être entre -100 et 100\n
        command_time_speed_control_motor_tacho:'id';port:'port';time:'time';speed:'speed';maxpower:'maxpower';brake:'brake' | 'port', 'speed' et 'maxpower' sont identiques, 'time' est le temps de fonctionnement en ms et 'brake' et 0 ou 1 (frein ou pas de frein à la fin)\n
        command_angle_speed_control_motor_tacho:'id';port:'port';angle:'angle';speed:'speed';maxpower:'maxpower';brake:'brake' | 'port', 'speed', 'maxpower' et 'brake' sont identiques, 'angle' est l'angle en degré de rotation du moteur par rapport à la position actuel (positif car c'est 'speed' qui détermine le sens de rotation)\n
        command_absolute_position_speed_control_motor_tacho:'id';port:'port';angle:'angle';speed:'speed';maxpower:'maxpower';brake:'brake' | 'port', 'speed', 'maxpower' et 'brake' sont identiques, 'angle' est l'angle en degré par rapport à la position initial au démarage du hub (positif ou négatif, 'speed' de préférence positif)\n
        commande d'écoute des messages :
        command_start_listen_motor_tacho:'id';port:'port' | 'port' est identique (A, B, C ou D, + code hex pour des hubs spécifiques), et command_close_listen_motor_tacho:'id';port:'port' renvoie la position du moteur à tachymètre actuel en degré (start l'active et close le désactive)\n
        command_start_listen_handset:'id' | command_close_listen_handset:'id' | permet de récupérer les boutons pressé par l'utilisateur,\nrenvoie : "center button down", "center button up", "all left button up", "center left button down", "+ left button down", "- left button down", "all right button up", "center right button down", "+ right button down", "- right button down"\n
        commande évolué ou non prise en compte, ce référer à la documentation officiel de Wirless protocol v3 LEGO powered up (c)\n
        passé des commandes évolués :\n
        command_output:'id';'codebyte' | 'codebyte' correspond aux bites que vous souhaité envoyé en hexadécimal par paquet de 2 (ex: 03 00 02 02 pour déconnecter le hub)\n
        command_listen:'id';port:'port';mode:'mode';state:'state' | envoie une commande d'écoute d'un port (A, B, C ou D, + code hex pour des hubs spécifiques comme 61, 62 ou 63 sur hub techinc pour avoir l'accéléromètre), 'mode' est un code hex sur un octet (01 sur capteur de couleur et de distance pour avoir la distance), 'state' est 0 ou 1 pour activé ou désactivé ces msg\n
        \npour plus d'info sur les commandes de bite tappez byte_info ou bite_info\n
        """
        return text_info
    
    elif line == "byte_info" or line == "bite_info" or line == "byte_info()" or line == "bite_info()":
        return test_byte_info
    
    elif line == "connexion_list" or line == "connection_list":
        hubs = await controller.scan()
        return "Hubs:" + ",".join(f"{addr}|{name}" for addr, name in hubs)

    elif line.startswith("start_connexion:") or line.startswith("start_connection:"):
        device_id = line.split(":", 1)[1]
        return await controller.connect(device_id)

    elif line.startswith("close_connexion:") or line.startswith("close_connection:"):
        device_id = line.split(":", 1)[1]
        return await controller.disconnect(device_id)

    elif line == "close_all_connexion" or line == "close_all_connection":
        return await controller.disconnect_all()

    elif line.startswith("command_output:"):
        try:
            _, rest = line.split(":", 1)
            device_id, hex_data = rest.split(";", 1)
            hex_data = hex_data.strip().strip('"').strip("'")
            data_bytes = bytes.fromhex(hex_data)
            return await controller.send_command(device_id, data_bytes)
        except Exception as e:
            return f"Erreur parsing command_output : {e}"

    elif line.startswith("Switch_Off_Hub:"):
        try:
            device_id = line.split(":", 1)[1]
            data_bytes = bytes([0x03, 0x00, 0x02, 0x01])
            return await controller.send_command(device_id, data_bytes)
        except Exception as e:
            return f"Erreur Switch_Off_Hub : {e}"
        
    elif line.startswith("command_hub_color:"):
        try:
            _, rest = line.split(":", 1)
            device_id, params = rest.split(";", 1)

            # parser les paramètres
            parts = params.split(";")
            args = {}
            for part in parts:
                k, v = part.split(":", 1)
                args[k.strip().lower()] = v.strip().strip("'").strip('"')

            port_str = args['port']
            code_int = int(args['code'])

            if not 0 <= code_int <= 10:
                return f"Code doit être entre 0 et 10 (pour la couleur car pas de rgb)"

            port_int = int(port_str, 16)  # port doit être donné sous forme d’int ou string de chiffre
            if not 0 <= port_int <= 255:
                return f"Port doit être entre 0 et 255 (généralement 32 ou 34 en fonction du hub)"

            code_byte = code_int & 0xFF
            port_byte = port_int & 0xFF

            data_bytes = bytes([
            0x08, 0x00, 0x81, port_int, 0x11, 0x51, 0x00, code_byte
            ])

            #print(data_bytes.hex().upper())

            return await controller.send_command(device_id, data_bytes)

        except Exception as e:
            return f"Erreur command_hub_color : {e}"
        
    elif line.startswith("command_power:"):
        try:
            _, rest = line.split(":", 1)
            device_id, params = rest.split(";", 1)

            # ensuite on parse params
            parts = params.split(";")
            args = {}
            for part in parts:
                k, v = part.split(":", 1)
                args[k.strip().lower()] = v.strip().strip("'").strip('"')

            port_letter = args['port'].upper()
            speed = int(args['speed'])

            port_map = {'A': 0x00, 'B': 0x01, 'C': 0x02, 'D': 0x03, 'a': 0x00, 'b': 0x01, 'c': 0x02, 'd': 0x03}
            if port_letter not in port_map:
                return f"Port inconnu : {port_letter}"
            port_code = port_map[port_letter]

            if not -100 <= speed <= 100:
                return f"Speed doit être entre -100 et 100"

            speed_byte = speed & 0xFF

            data_bytes = bytes([
                0x08, 0x00, 0x81, port_code, 0x11, 0x51, 0x00, speed_byte
            ])

            return await controller.send_command(device_id, data_bytes)
        except Exception as e:
            return f"Erreur command_power : {e}"

    elif line.startswith("command_power_motor_tacho:"):
        try:
            _, rest = line.split(":", 1)
            device_id, params = rest.split(";", 1)

            # ensuite on parse params
            parts = params.split(";")
            args = {}
            for part in parts:
                k, v = part.split(":", 1)
                args[k.strip().lower()] = v.strip().strip("'").strip('"')

            port_letter = args['port'].upper()
            speed = int(args['speed'])

            port_map = {'A': 0x00, 'B': 0x01, 'C': 0x02, 'D': 0x03, 'a': 0x00, 'b': 0x01, 'c': 0x02, 'd': 0x03}
            if port_letter not in port_map:
                return f"Port inconnu : {port_letter}"
            port_code = port_map[port_letter]

            if not -100 <= speed <= 100:
                return f"Speed doit être entre -100 et 100"

            speed_byte = speed & 0xFF

            data_bytes = bytes([
                0x08, 0x00, 0x81, port_code, 0x11, 0x51, 0x01, speed_byte
            ])

            return await controller.send_command(device_id, data_bytes)
        except Exception as e:
            return f"Erreur command_power_motor_tacho : {e}"

    elif line.startswith("command_speed_control_motor_tacho:"):
        try:
            _, rest = line.split(":", 1)
            device_id, params = rest.split(";", 1)

            # parser les paramètres
            parts = params.split(";")
            args = {}
            for part in parts:
                k, v = part.split(":", 1)
                args[k.strip().lower()] = v.strip().strip("'").strip('"')

            port_letter = args['port'].upper()
            speed = int(args['speed'])
            maxpower = int(args['maxpower'])

            # vérifier les valeurs
            port_map = {'A': 0x00, 'B': 0x01, 'C': 0x02, 'D': 0x03, 'a': 0x00, 'b': 0x01, 'c': 0x02, 'd': 0x03}
            if port_letter not in port_map:
                return f"Port inconnu : {port_letter}"
            port_code = port_map[port_letter]

            if not -100 <= speed <= 100:
                return f"Speed doit être entre -100 et 100"
            if not -100 <= maxpower <= 100:
                return f"Maxpower doit être entre -100 et 100"

            speed_byte = speed & 0xFF
            maxpower_byte = maxpower & 0xFF

            data_bytes = bytes([
            0x0A, 0x00, 0x81, port_code, 0x11, 0x07, speed_byte, maxpower_byte, 0x00
            ])

            return await controller.send_command(device_id, data_bytes)

        except Exception as e:
            return f"Erreur command_speed_control_motor_tacho : {e}"

    elif line.startswith("command_time_speed_control_motor_tacho:"):
        try:
            _, rest = line.split(":", 1)
            device_id, params = rest.split(";", 1)

            # parser les paramètres
            parts = params.split(";")
            args = {}
            for part in parts:
                k, v = part.split(":", 1)
                args[k.strip().lower()] = v.strip().strip("'").strip('"')

            # Port
            port_letter = args['port'].upper()
            ports = {'A': 0x00, 'B': 0x01, 'C': 0x02, 'D': 0x03, 'a': 0x00, 'b': 0x01, 'c': 0x02, 'd': 0x03}
            if port_letter not in ports:
                return f"Port doit être A, B, C ou D"
            port_byte = ports[port_letter]

            # Time
            time_ms = int(args['time'])
            if not (0 <= time_ms <= 65535):
                return f"Time doit être entre 0 et 65535 ms"
            time_bytes = time_ms.to_bytes(2, byteorder='little', signed=False)

            # Speed
            speed = int(args['speed'])
            if not -100 <= speed <= 100:
                return f"Speed doit être entre -100 et 100"
            speed_byte = speed & 0xFF if speed >= 0 else (256 + speed)

            # Maxpower
            maxpower = int(args['maxpower'])
            if not -100 <= maxpower <= 100:
                return f"Maxpower doit être entre -100 et 100"
            maxpower_byte = maxpower & 0xFF if maxpower >= 0 else (256 + maxpower)

            # Brake
            brake = int(args['brake'])
            if brake == 0:
                brake_byte = 0x00
            elif brake == 1:
                brake_byte = 0x7F
            else:
                return f"Brake doit être 0 ou 1"

            # Construire la commande
            data_bytes = bytes([
            0x0C, 0x00, 0x81, port_byte, 0x11, 0x09,
            time_bytes[0], time_bytes[1],
            speed_byte, maxpower_byte, brake_byte, 0x00
            ])

            #print(data_bytes.hex().upper())
            return await controller.send_command(device_id, data_bytes)

        except Exception as e:
            return f"Erreur command_time_speed_control_motor_tacho : {e}"

    elif line.startswith("command_angle_speed_control_motor_tacho:"):
        try:
            _, rest = line.split(":", 1)
            device_id, params = rest.split(";", 1)

            # parser les paramètres
            parts = params.split(";")
            args = {}
            for part in parts:
                k, v = part.split(":", 1)
                args[k.strip().lower()] = v.strip().strip("'").strip('"')

            # Port
            port_letter = args['port'].upper()
            ports = {'A': 0x00, 'B': 0x01, 'C': 0x02, 'D': 0x03, 'a': 0x00, 'b': 0x01, 'c': 0x02, 'd': 0x03}
            if port_letter not in ports:
                return f"Port doit être A, B, C ou D"
            port_byte = ports[port_letter]

            # Angle
            angle = int(args['angle'])
            if not (0 <= angle <= 0xFFFFFFFF):
                return f"Angle doit être entre 0 et 4294967295"
            angle_bytes = angle.to_bytes(4, byteorder='little', signed=False)


            # Speed
            speed = int(args['speed'])
            if not -100 <= speed <= 100:
                return f"Speed doit être entre -100 et 100"
            speed_byte = speed & 0xFF if speed >= 0 else (256 + speed)

            # Maxpower
            maxpower = int(args['maxpower'])
            if not -100 <= maxpower <= 100:
                return f"Maxpower doit être entre -100 et 100"
            maxpower_byte = maxpower & 0xFF if maxpower >= 0 else (256 + maxpower)

            # Brake
            brake = int(args['brake'])
            if brake == 0:
                brake_byte = 0x00
            elif brake == 1:
                brake_byte = 0x7F
            else:
                return f"Brake doit être 0 ou 1"

            # Construire la commande
            data_bytes = bytes([
            0x0E, 0x00, 0x81, port_byte, 0x11, 0x0B,
            angle_bytes[0], angle_bytes[1], angle_bytes[2], angle_bytes[3],
            speed_byte, maxpower_byte, brake_byte, 0x00
            ])

            # print(data_bytes.hex().upper())
            return await controller.send_command(device_id, data_bytes)

        except Exception as e:
            return f"Erreur command_angle_speed_control_motor_tacho : {e}"
        
    elif line.startswith("command_absolute_position_speed_control_motor_tacho:"):
        try:
            _, rest = line.split(":", 1)
            device_id, params = rest.split(";", 1)

            # parser les paramètres
            parts = params.split(";")
            args = {}
            for part in parts:
                k, v = part.split(":", 1)
                args[k.strip().lower()] = v.strip().strip("'").strip('"')

            # Port
            port_letter = args['port'].upper()
            ports = {'A': 0x00, 'B': 0x01, 'C': 0x02, 'D': 0x03, 'a': 0x00, 'b': 0x01, 'c': 0x02, 'd': 0x03}
            if port_letter not in ports:
                return f"Port doit être A, B, C ou D"
            port_byte = ports[port_letter]

            angle = int(args['angle'])
            if not (-2147483648 <= angle <= 2147483647):
                return f"Angle doit être entre -2147483648 et 2147483647"
            angle_bytes = angle.to_bytes(4, byteorder='little', signed=True)


            # Speed
            speed = int(args['speed'])
            if not -100 <= speed <= 100:
                return f"Speed doit être entre -100 et 100"
            speed_byte = speed & 0xFF if speed >= 0 else (256 + speed)

            # Maxpower
            maxpower = int(args['maxpower'])
            if not -100 <= maxpower <= 100:
                return f"Maxpower doit être entre -100 et 100"
            maxpower_byte = maxpower & 0xFF if maxpower >= 0 else (256 + maxpower)

            # Brake
            brake = int(args['brake'])
            if brake == 0:
                brake_byte = 0x00
            elif brake == 1:
                brake_byte = 0x7F
            else:
                return f"Brake doit être 0 ou 1"

            # Construire la commande
            data_bytes = bytes([
            0x0E, 0x00, 0x81, port_byte, 0x11, 0x0D,
            angle_bytes[0], angle_bytes[1], angle_bytes[2], angle_bytes[3],
            speed_byte, maxpower_byte, brake_byte, 0x00
            ])

            # print(data_bytes.hex().upper())
            return await controller.send_command(device_id, data_bytes)

        except Exception as e:
            return f"Erreur command_absolute_position_speed_control_motor_tacho : {e}"

    elif line.startswith("command_listen:"):
        try:
            _, rest = line.split(":", 1)
            device_id, params = rest.split(";", 1)

            # parser les paramètres
            parts = params.split(";")
            args = {}
            for part in parts:
                k, v = part.split(":", 1)
                args[k.strip().lower()] = v.strip().strip("'").strip('"')

            # Port (A,B,C,D ou hex)
            port_str = args['port'].strip()

            ports = {'A': 0x00, 'B': 0x01, 'C': 0x02, 'D': 0x03,
             'a': 0x00, 'b': 0x01, 'c': 0x02, 'd': 0x03}

            if port_str in ports:
                port_byte = ports[port_str]
            else:
                try:
                    # Essayer de parser comme nombre hexadécimal
                    if port_str.lower().startswith('0x'):
                        port_byte = int(port_str, 16)
                    else:
                        port_byte = int(port_str, 16)
                    if not (0 <= port_byte <= 0xFF):
                        return f"Port hex doit être entre 00 et FF"
                except Exception:
                    return f"Port doit être A, B, C, D ou un nombre hexadécimal"

            # Mode (hex)
            mode = int(args['mode'], 16)
            if not (0 <= mode <= 0xFF):
                return f"Mode doit être une valeur hex valide entre 00 et FF"
            mode_byte = mode & 0xFF

            # State (0,1,false,true)
            state_str = args['state'].lower()
            if state_str in ['1', 'true']:
                state_byte = 0x01
            elif state_str in ['0', 'false']:
                state_byte = 0x00
            else:
                return f"State doit être 0, 1, true ou false"

            # Construire la commande
            data_bytes = bytes([
            0x0A, 0x00, 0x41, port_byte, mode_byte,
            0x01, 0x00, 0x00, 0x00, state_byte
            ])

            # print(data_bytes.hex().upper())
            return await controller.send_command(device_id, data_bytes)

        except Exception as e:
            return f"Erreur command_listen : {e}"

    elif line.startswith("command_start_listen_motor_tacho:"):
        try:
            _, rest = line.split(":", 1)
            device_id, params = rest.split(";", 1)

            # parser les paramètres
            parts = params.split(";")
            args = {}
            for part in parts:
                k, v = part.split(":", 1)
                args[k.strip().lower()] = v.strip().strip("'").strip('"')

            # Port (A,B,C,D ou hex)
            port_str = args['port'].strip()

            ports = {'A': 0x00, 'B': 0x01, 'C': 0x02, 'D': 0x03,
                 'a': 0x00, 'b': 0x01, 'c': 0x02, 'd': 0x03}

            if port_str in ports:
                port_byte = ports[port_str]
                port_letter = port_str.upper()
            else:
                try:
                    # Essayer de parser comme nombre hexadécimal
                    if port_str.lower().startswith('0x'):
                        port_byte = int(port_str, 16)
                    else:
                        port_byte = int(port_str, 16)
                    if not (0 <= port_byte <= 0xFF):
                        return f"Port hex doit être entre 00 et FF"
                    port_letter = '?'  # inconnu
                except Exception:
                    return f"Port doit être A, B, C, D ou un nombre hexadécimal"

            # Construire la commande : 0A 00 41 <port> 02 01 00 00 00 01
            data_bytes = bytes([
            0x0A, 0x00, 0x41, port_byte, 0x02,
            0x01, 0x00, 0x00, 0x00, 0x01
            ])

            # Ajouter à la liste
            controller.get_motor_absolute_position.append((True, device_id, port_letter))

            return await controller.send_command(device_id, data_bytes)

        except Exception as e:
            return f"Erreur command_start_listen_motor_tacho : {e}"


    elif line.startswith("command_close_listen_motor_tacho:"):
        try:
            _, rest = line.split(":", 1)
            device_id, params = rest.split(";", 1)

            # parser les paramètres
            parts = params.split(";")
            args = {}
            for part in parts:
                k, v = part.split(":", 1)
                args[k.strip().lower()] = v.strip().strip("'").strip('"')

            # Port (A,B,C,D ou hex)
            port_str = args['port'].strip()

            ports = {'A': 0x00, 'B': 0x01, 'C': 0x02, 'D': 0x03,
                 'a': 0x00, 'b': 0x01, 'c': 0x02, 'd': 0x03}

            if port_str in ports:
                port_byte = ports[port_str]
                port_letter = port_str.upper()
            else:
                try:
                    if port_str.lower().startswith('0x'):
                        port_byte = int(port_str, 16)
                    else:
                        port_byte = int(port_str, 16)
                    if not (0 <= port_byte <= 0xFF):
                        return f"Port hex doit être entre 00 et FF"
                    port_letter = '?'  # inconnu
                except Exception:
                    return f"Port doit être A, B, C, D ou un nombre hexadécimal"

            # Construire la commande : 0A 00 41 <port> 02 01 00 00 00 00
            data_bytes = bytes([
            0x0A, 0x00, 0x41, port_byte, 0x02,
            0x01, 0x00, 0x00, 0x00, 0x00
            ])

            # Retirer de la liste
            controller.get_motor_absolute_position = [
            tup for tup in controller.get_motor_absolute_position
            if not (tup[0] and tup[1] == device_id and tup[2] == port_letter)
            ]

            return await controller.send_command(device_id, data_bytes)

        except Exception as e:
            return f"Erreur command_close_listen_motor_tacho : {e}"

    elif line.startswith("command_start_listen_handset:"):
        try:
            _, rest = line.split(":", 1)
            device_id = rest.strip().strip("'").strip('"')

            # Ajouter dans la liste si pas déjà
            if device_id not in controller.get_msg_handset:
                controller.get_msg_handset.append(device_id)

            # Envoyer les deux commandes
            cmds = [
            bytes([0x0A, 0x00, 0x41, 0x01, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01]),
            bytes([0x0A, 0x00, 0x41, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01]),
            ]

            results = []
            for cmd in cmds:
                res = await controller.send_command(device_id, cmd)
                results.append(res)

            return "\n".join(results)

        except Exception as e:
            return f"Erreur command_start_listen_handset : {e}"

    elif line.startswith("command_close_listen_handset:"):
        try:
            _, rest = line.split(":", 1)
            device_id = rest.strip().strip("'").strip('"')

            # Retirer de la liste
            if device_id in controller.get_msg_handset:
                controller.get_msg_handset.remove(device_id)

            # Envoyer les deux commandes pour arrêter d'écouter
            cmds = [
            bytes([0x0A, 0x00, 0x41, 0x01, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]),
            bytes([0x0A, 0x00, 0x41, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00]),
            ]

            results = []
            for cmd in cmds:
                res = await controller.send_command(device_id, cmd)
                results.append(res)

            return "\n".join(results)

        except Exception as e:
            return f"Erreur command_close_listen_handset : {e}"

    else:
        return f"Commande inconnue : {line}"

async def main_loop():
    controller = LegoController()

    print("Controller LEGO Powered up (c) prêt à recevoir des commandes sur stdin...")
    loop = asyncio.get_event_loop()

    while True:
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            break

        response = await parse_command(controller, line)
        print(response)
        sys.stdout.flush()
        
asyncio.run(main_loop())