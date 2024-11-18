"""\
GLO-2000 Travail pratique 4 - Serveur
Noms et numéros étudiants:
-
-
-
"""

import hashlib
import hmac
import json
import os
import select
import socket
import sys
import re
import glob
import datetime

import glosocket
import gloutils


class Server:
    """Serveur mail @glo2000.ca."""

    def __init__(self) -> None:
        """
        Prépare le socket du serveur `_server_socket`
        et le met en mode écoute.

        Prépare les attributs suivants:
        - `_client_socs` une liste des sockets clients.
        - `_logged_users` un dictionnaire associant chaque
            socket client à un nom d'utilisateur.

        S'assure que les dossiers de données du serveur existent.
        """
        # self._server_socket
        # self._client_socs
        # self._logged_users
        # ...

        # Creation du socket server
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._server_socket.bind(("127.0.0.1", gloutils.APP_PORT))
            self._server_socket.listen()
        except OverflowError:
            sys.exit("Port has bad value")
        except socket.gaierror:
            sys.exit("Temporary failure in name resolution of the destination")
        except PermissionError:
            sys.exit("Port's permission is denied")
        
        print(f'Server listening to port : {gloutils.APP_PORT}')

        # Intialise les dicts + list
        self._client_socs = []
        self._logged_users = {}
        
        # Verifie l'existence de SERVER_DATA_DIR et SERVER_LOST_DIR
        data_dir = gloutils.SERVER_DATA_DIR
        lost_dir = os.path.join(gloutils.SERVER_DATA_DIR, gloutils.SERVER_LOST_DIR)
        
        if  not os.path.exists(data_dir):
            os.makedirs(data_dir)
        if not os.path.exists(lost_dir):
            os.makedirs(lost_dir)

    def cleanup(self) -> None:
        """Ferme toutes les connexions résiduelles."""
        for client_soc in self._client_socs:
            self._remove_client(client_soc)
            
        self._server_socket.close()
        self._client_socs = []
        self._logged_users = []

    def _accept_client(self) -> None:
        """Accepte un nouveau client."""
        new_soc, _ = self._server_socket.accept()
        self._client_socs.append(new_soc)
        print(f"Accepte client {new_soc}")

    def _remove_client(self, client_soc: socket.socket) -> None:
        """Retire le client des structures de données et ferme sa connexion."""
        self._logout(client_soc)
        if client_soc in self._client_socs:
            self._client_socs.remove(client_soc)
            print(f"Remove client {client_soc}")
        client_soc.close()

    def _create_account(self, client_soc: socket.socket,
                        payload: gloutils.AuthPayload
                        ) -> gloutils.GloMessage:
        """
        Crée un compte à partir des données du payload.

        Si les identifiants sont valides, créee le dossier de l'utilisateur,
        associe le socket au nouvel l'utilisateur et retourne un succès,
        sinon retourne un message d'erreur.
        """
        
        print(f"Creating account : {client_soc}")
        
        output_message : gloutils.GloMessage = gloutils.GloMessage(
            header=gloutils.Headers.OK
        )
        
        users_name_lower = [x.lower() for x in self._logged_users.values()]
        username = payload["username"].lower()
        
        if not re.search(r"^[a-zA-Z0-9_.-]+$", payload["username"]):
            output_message = gloutils.GloMessage(
                header=gloutils.Headers.ERROR, 
                payload=gloutils.ErrorPayload(
                    error_message="Le nom d'utilisateur est invalide, il contient un caractere invalide, veuillez utiliser seulement des caractères alpahnumériques ou des ., - ou _ ."
                )
            )
        
        elif username in users_name_lower:
            output_message = gloutils.GloMessage(
                header=gloutils.Headers.ERROR, 
                payload=gloutils.ErrorPayload(
                    error_message="Le nom d'utilisateur est déjà pris. Veuillez entrer un autre nom d'utilisateur."
                )
            )
        
        elif not re.search(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{10,}$",payload["password"] ):
            output_message = gloutils.GloMessage(
                header=gloutils.Headers.ERROR, 
                payload=gloutils.ErrorPayload(
                    error_message="Le mot de passe n'est pas assez sécurisé. Veuillez entrer un mot de passe d'au moins 10 caractères, avec au moins un chiffre, une majuscule et une minuscule."
                )
            )
        
        # If no error, deal with the successful account creation
        elif output_message["header"] == gloutils.Headers.OK:
            new_folder_path = os.path.join(gloutils.SERVER_DATA_DIR, username)
            password_file_path = os.path.join(new_folder_path, gloutils.PASSWORD_FILENAME)
            hashed_password = hashlib.sha3_512(payload["password"].encode('utf-8'))
            os.makedirs(new_folder_path, exist_ok=True)
            
            # Saves passowrd to user folder
            with open(password_file_path, 'w') as file:
                file.write(hashed_password.hexdigest())
            
            # Updates the logged users dict
            self._logged_users[client_soc] = payload["username"].lower()
        
        return output_message

    def _login(self, client_soc: socket.socket, payload: gloutils.AuthPayload
               ) -> gloutils.GloMessage:
        """
        Vérifie que les données fournies correspondent à un compte existant.

        Si les identifiants sont valides, associe le socket à l'utilisateur et
        retourne un succès, sinon retourne un message d'erreur.
        """
        
        print(f"Logging into account : {client_soc}")
        
        output_message = gloutils.GloMessage(
            header=gloutils.Headers.OK
        )
        
        folderpaths = glob.glob(gloutils.SERVER_DATA_DIR, "*")
        folderpaths_name = [os.path.basename(x).lower() for x in folderpaths]
        username = payload["username"].lower()
        
        if not username in folderpaths_name:
            output_message = gloutils.GloMessage(
                header=gloutils.Headers.ERROR,
                payload=gloutils.ErrorPayload(
                    error_message="Il n'y a pas de compte associé à ce nom d'utilisateur."
                )
            )
        else:
            userfile_path = os.path.join(gloutils.SERVER_DATA_DIR, username)
            password_path = os.path.join(userfile_path, gloutils.PASSWORD_FILENAME)
            with open(password_path, "r") as file:
                expected_hash = file.readline()
                encoded_text = payload["password"].encode("utf-8")
                hasher = hashlib.sha3_512()
                hasher.update(encoded_text)
                
                if hmac.compare_digest(hasher.hexdigest(), expected_hash):
                    # updates the dict with the logged in user
                    self._logged_users[client_soc] = username
                else:
                    output_message = gloutils.GloMessage(
                        header=gloutils.Headers.ERROR,
                        payload=gloutils.ErrorPayload(
                            error_message="Mot de passe invalide."
                    )
                )
                
        return output_message

    def _logout(self, client_soc: socket.socket) -> None:
        """Déconnecte un utilisateur."""
        if client_soc in self._logged_users.keys():
            del self._logged_users[client_soc]

    def _get_email_list(self, client_soc: socket.socket
                        ) -> gloutils.GloMessage:
        """
        Récupère la liste des courriels de l'utilisateur associé au socket.
        Les éléments de la liste sont construits à l'aide du gabarit
        SUBJECT_DISPLAY et sont ordonnés du plus récent au plus ancien.

        Une absence de courriel n'est pas une erreur, mais une liste vide.
        """
        email_list = self._get_sorted_email_list(client_soc)
        email_list_str = []
        
        for i, email in enumerate(email_list):
            email_list_str.append(gloutils.SUBJECT_DISPLAY.format(
                number=i+1, # numbering starts at 1
                sender=email["sender"],
                subject=email["subject"],
                date=email["date"]
            ))
        
        output_message = gloutils.GloMessage(
            header=gloutils.Headers.OK,
            payload=gloutils.EmailListPayload(
                email_list = email_list_str
            )
        )
        
        return output_message

    def _get_email(self, client_soc: socket.socket,
                   payload: gloutils.EmailChoicePayload
                   ) -> gloutils.GloMessage:
        """
        Récupère le contenu de l'email dans le dossier de l'utilisateur associé
        au socket.
        """
        index = payload["choice"] - 1 # because numering on client side, starts at 1
        email_list = self._get_sorted_email_list(client_soc)
        
        output_message = gloutils.GloMessage(
            header=gloutils.Headers.OK,
            payload=email_list[index]
        )
        
        return output_message

    def _get_stats(self, client_soc: socket.socket) -> gloutils.GloMessage:
        """
        Récupère le nombre de courriels et la taille du dossier et des fichiers
        de l'utilisateur associé au socket.
        """
        
        email_list = self._get_sorted_email_list(client_soc)
        username = self._logged_users[client_soc]
        folder_size = 0
        user_folder = os.path.join(gloutils.SERVER_DATA_DIR, username)
        for path, dirs, files in os.walk(user_folder):
            for f in files:
                file_path = os.path.join(path, f)
                folder_size += os.path.getsize(file_path)
                
        output_message = gloutils.GloMessage(
            header=gloutils.Headers.OK,
            payload=gloutils.StatsPayload(
                count=len(email_list),
                size=folder_size,
            )
        )
        
        return output_message
        

    def _send_email(self, payload: gloutils.EmailContentPayload
                    ) -> gloutils.GloMessage:
        """
        Détermine si l'envoi est interne ou externe et:
        - Si l'envoi est interne, écris le message tel quel dans le dossier
        du destinataire.
        - Si le destinataire n'existe pas, place le message dans le dossier
        SERVER_LOST_DIR et considère l'envoi comme un échec.
        - Si le destinataire est externe, considère l'envoi comme un échec.

        Retourne un messange indiquant le succès ou l'échec de l'opération.
        """
        output_message = gloutils.GloMessage(
            header=gloutils.Headers.OK,
        )
        
        if not re.search(rf"{gloutils.SERVER_DOMAIN}$", payload["destination"]):
            output_message = gloutils.GloMessage(
                header=gloutils.Headers.ERROR,
                payload=gloutils.ErrorPayload(
                    error_message="Le destinataire est un destinataire externe. Veuillez communiquer seulement à l'interne"
                )
            )
        else:
            nom_destinataire = payload["destination"][:-len(gloutils.SERVER_DOMAIN)].lower() # remove the SERVER_DOMAIN ending
            folderpaths = glob.glob(gloutils.SERVER_DATA_DIR)
            folderpaths_name = [os.path.basename(x).lower() for x in folderpaths]
            if not nom_destinataire in folderpaths_name:
                output_message = gloutils.GloMessage(
                    header=gloutils.Headers.ERROR,
                    payload=gloutils.ErrorPayload(
                        error_message="Le destinataire n'existe pas à l'interne."
                    )
                )
                
                lost_path = os.path.join(gloutils.SERVER_DATA_DIR, gloutils.SERVER_LOST_DIR)
                lost_file = os.path.join(lost_path, self._get_email_name(nom_destinataire, payload["date"]))
                
                with open(lost_file, 'w') as file:
                    json.dumps(payload, file, ensure_ascii=False, indent=4)
            else:
                email_path = os.path.join(gloutils.SERVER_DATA_DIR, nom_destinataire)
                email_file = os.path.join(email_path, self._get_email_name(nom_destinataire, payload["date"]))
                
                with open(email_file, 'w') as file:
                    json.dumps(payload, file, ensure_ascii=False, indent=4)
                    
        return output_message
    
    def _get_email_name(self, destinataire:str, date:str) -> str:
        return f"{destinataire}_{date}"
    
    def _sort_email_list(self, email_list : list[gloutils.EmailContentPayload]):
        return email_list.sort(key=lambda date: datetime.strptime(date, "%a, %d %b %Y %H:%M:%S %z"))

    def _get_sorted_email_list(self, client_soc : socket.socket) -> list[gloutils.EmailContentPayload]:
        username = self._logged_users[client_soc]
        user_path = os.path.join(gloutils.SERVER_DATA_DIR, username)
        json_list = glob.glob(os.path.join(user_path, "*.json"))
        email_list : list[gloutils.EmailContentPayload] = []
        for email_file in json_list:
            with open(email_file, 'r') as file:
                email: gloutils.EmailContentPayload = json.loads(file)
                email_list.append(email)
        
        # sorting the email list by date
        email_list:list[gloutils.EmailContentPayload] = self._sort_email_list(email_list)
        return email_list
    
    def _try_send_message(self, destination: socket.socket, message:str) -> None:
        try:
            glosocket.snd_mesg(destination, message)
        except:
            self._remove_client(destination)
        
    def _process_client(self, client_soc: socket.socket) -> None:
        try:
            client_message = glosocket.recv_mesg(client_soc)
        except glosocket.GLOSocketError:
            self._remove_client(client_soc)
            return
        
        client_message : gloutils.GloMessage = json.loads(client_message)
        
        if client_message["header"] == gloutils.Headers.AUTH_REGISTER:
            send_message = self._create_account(client_soc, client_message["payload"])
            
            if send_message["header"] == gloutils.Headers.ERROR:
                message_data = json.dumps(send_message)
                self._try_send_message(client_soc, message_data)
                return
                
            send_message = self._login(client_soc, client_message["payload"])
            message_data = json.dumps(send_message)
            self._try_send_message(client_soc, message_data)
            
        elif client_message["header"] == gloutils.Headers.AUTH_LOGIN:
            send_message = self._login(client_soc, client_message["payload"])
            message_data = json.dumps(send_message)
            self._try_send_message(client_soc, message_data)
            
        elif client_message["header"] == gloutils.Headers.AUTH_LOGOUT:
            self._logout(client_soc)
            send_message = gloutils.GloMessage(
                header=gloutils.Headers.OK
            )
            message_data = json.dumps(send_message)
            self._try_send_message(client_soc, message_data)
            
        elif client_message["header"] == gloutils.Headers.BYE:
            self._remove_client(client_soc)
            
        elif client_message["header"] == gloutils.Headers.INBOX_READING_REQUEST:
            send_message = self._get_email_list(client_soc)
            message_data = json.dumps(send_message)
            self._try_send_message(client_soc, message_data)
            
        elif client_message["header"] == gloutils.Headers.INBOX_READING_CHOICE:
            send_message = self._get_email(client_soc, client_message["payload"])
            message_data = json.dumps(send_message)
            self._try_send_message(client_soc, message_data)
            
        elif client_message["header"] == gloutils.Headers.EMAIL_SENDING:
            send_message = self._send_email(client_message["payload"])
            message_data = json.dumps(send_message)
            self._try_send_message(client_soc, message_data)
        
        elif client_message["header"] == gloutils.Headers.STATS_REQUEST:
            send_message = self._get_stats(client_soc)
            message_data = json.dumps(send_message)
            self._try_send_message(client_soc, message_data)
            
              
    def run(self):
        """Point d'entrée du serveur."""
        waiters = []
        while True:
            # Select readable sockets
            result = select.select([self._server_socket] + self._client_socs, [], [])
            waiters: list[socket.socket] = result[0]
            for waiter in waiters:
                # Handle sockets
                if waiter == self._server_socket:
                    self._accept_client()
                else:
                    self._process_client(waiter)
                
def _main() -> int:
    server = Server()
    try:
        server.run()
    except KeyboardInterrupt:
        server.cleanup()
    return 0


if __name__ == '__main__':
    sys.exit(_main())
