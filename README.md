LEGO Powered Up Controller (non officiel)
⚠️ Ce projet n’est aucunement lié au groupe LEGO®.
Créé par argentropcher grâce à la documentation officielle LEGO.
Modification et vente interdites – tout droit réservé.

✨ Présentation
Cette application permet de contrôler les hubs LEGO Powered Up via Bluetooth Low Energy (BLE).
Elle repose sur l’UUID LEGO Powered Up :

Copier
Modifier
00001624-1212-efde-1623-785feabcd123
Si LEGO change cet UUID, il faudra créer un fichier char_uuid_lego_controller.txt contenant le nouvel UUID.

⚙️ Commandes principales
🔗 Connexion aux hubs
Commande	Description
connexion_list ou connection_list	Liste les hubs allumés et affiche leur ID unique (ex: 00:16:53:AD:00:73).
start_connexion:'id' ou start_connection:'id'	Connecte le hub à l'ordinateur.
close_connexion:'id' ou close_connection:'id'	Déconnecte le hub du Bluetooth de l'ordinateur.

🎨 Contrôle des hubs
Commande	Description
Switch_Off_Hub:'id'	Éteint proprement le hub.
command_hub_color:'id';port:'port';code:'code'	Change la couleur de la LED du hub (port: 32 ou 34, code: 0–10).
command_power:'id';port:'port';speed:'speed'	Contrôle un moteur ou une LED (port: A/B/C/D, speed: -100 à 100).
command_power_motor_tacho:'id';port:'port';speed:'speed'	Idem mais uniquement pour les moteurs à tachymètre.
command_speed_control_motor_tacho:'id';port:'port';speed:'speed';maxpower:'maxpower'	Contrôle la vitesse avec puissance max.
command_time_speed_control_motor_tacho:'id';port:'port';time:'time';speed:'speed';maxpower:'maxpower';brake:'brake'	Fait tourner le moteur pendant time ms, brake = 0/1.
command_angle_speed_control_motor_tacho:'id';port:'port';angle:'angle';speed:'speed';maxpower:'maxpower';brake:'brake'	Fait tourner le moteur sur angle degrés par rapport à la position actuelle.
command_absolute_position_speed_control_motor_tacho:'id';port:'port';angle:'angle';speed:'speed';maxpower:'maxpower';brake:'brake'	Fait tourner le moteur jusqu’à un angle absolu par rapport à la position initiale.

🎛 Écoute des messages
Commande	Description
command_start_listen_motor_tacho:'id';port:'port'	Commence à écouter la position d’un moteur à tachymètre.
command_close_listen_motor_tacho:'id';port:'port'	Arrête l’écoute.
command_start_listen_handset:'id'	Récupère les boutons pressés sur une manette Powered Up.
command_close_listen_handset:'id'	Arrête l’écoute des boutons.

Exemples de messages reçus :

"center button down" / "center button up"

"+ left button down", "- right button down", etc.

🛠 Commandes avancées
Commande	Description
command_output:'id';'codebyte'	Envoie directement une suite d’octets en hexadécimal (ex: 03 00 02 02 pour déconnecter le hub).
command_listen:'id';port:'port';mode:'mode';state:'state'	Active ou désactive l’écoute sur un port précis avec un mode donné (en hex).

📄 Pour plus de détails sur les commandes bas niveau, voir la documentation officielle LEGO Wireless Protocol v3.

ℹ️ Infos supplémentaires
Pour plus d’info sur les commandes en bytes : tapez byte_info ou bite_info dans l’application.

Compatible avec les hubs LEGO Powered Up, Control+, et Boost (selon support BLE et UUID).

🧑‍💻 Auteur :

Créé par argentropcher
Compte Google associé : argentropcher
