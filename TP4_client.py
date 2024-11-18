"""\
GLO-2000 Travail pratique 4 - Client
Noms et numéros étudiants: Louis-Etienne Messier (537 131 157), Jose Andres Chia Ortiz (536 896 836), Fayssal Laghcha (536 856 578)
-
-
-
"""

import argparse
import getpass
import json
import socket
import sys
import re

import glosocket
import gloutils


class Client:
    """Client pour le serveur mail @glo2000.ca."""

    def __init__(self, destination: str) -> None:
        """
        Prépare et connecte le socket du client `_socket`.

        Prépare un attribut `_username` pour stocker le nom d'utilisateur
        courant. Laissé vide quand l'utilisateur n'est pas connecté.
        """
        port = gloutils.APP_PORT
        
        self._client_soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._username = ""

        try:
            self._client_soc.connect((destination, port))
        except OverflowError:
            sys.exit("Port has bad value")
        except socket.gaierror:
            sys.exit("Temporary failure in name resolution of the destination")
        except ConnectionRefusedError:
            sys.exit("Port's connection is refused")


    def _register(self) -> None:
        """
        Demande un nom d'utilisateur et un mot de passe et les transmet au
        serveur avec l'entête `AUTH_REGISTER`.

        Si la création du compte s'est effectuée avec succès, l'attribut
        `_username` est mis à jour, sinon l'erreur est affichée.
        """
        _username = input("Entrez un nom d'utilisateur: ")
        _password = getpass.getpass("Entrez un mot de passe: ")
        
        message = gloutils.GloMessage(
            header=gloutils.Headers.AUTH_REGISTER,
            payload=gloutils.AuthPayload(
                username=_username,
                password=_password
            )
        )
        message_data = json.dumps(message)
        self._try_send_mesg(self._client_soc, message_data)
        
        
        reply_data = glosocket.recv_mesg(self._client_soc)
        reply  : gloutils.GloMessage = json.loads(reply_data)

        if reply["header"] ==  gloutils.Headers.OK:
            self._username = _username # utilisateur authentifie
        elif reply["header"] == gloutils.Headers.ERROR:
            payload : gloutils.ErrorPayload = reply['payload']
            print(payload["error_message"]) # affiche erreur

    def _login(self) -> None:
        """
        Demande un nom d'utilisateur et un mot de passe et les transmet au
        serveur avec l'entête `AUTH_LOGIN`.

        Si la connexion est effectuée avec succès, l'attribut `_username`
        est mis à jour, sinon l'erreur est affichée.
        """
        _username = input("Entrez un nom d'utilisateur: ")
        _password = getpass.getpass("Entrez un mot de passe: ")
        
        message = gloutils.GloMessage(
            header=gloutils.Headers.AUTH_LOGIN,
            payload=gloutils.AuthPayload(
                username=_username,
                password=_password
            )
        )
        message_data = json.dumps(message)
        self._try_send_mesg(self._client_soc, message_data)
        
        reply_data = glosocket.recv_mesg(self._client_soc)
        reply  : gloutils.GloMessage = json.loads(reply_data)

        if reply["header"] ==  gloutils.Headers.OK:
            print()
            print("Connexion avec succès!")
            print(f"Bonjour {_username}")
            self._username = _username # utilisateur authentifie
        elif reply["header"] == gloutils.Headers.ERROR:
            payload : gloutils.ErrorPayload = reply['payload']
            print(payload["error_message"]) # affiche erreur


    def _quit(self) -> None:
        """
        Préviens le serveur de la déconnexion avec l'entête `BYE` et ferme le
        socket du client.
        """
        message = gloutils.GloMessage(
            header=gloutils.Headers.BYE,
        )
        message_data = json.dumps(message)
        self._try_send_mesg(self._client_soc, message_data)
        
        self._client_soc.close()

    def _read_email(self) -> None:
        """
        Demande au serveur la liste de ses courriels avec l'entête
        `INBOX_READING_REQUEST`.

        Affiche la liste des courriels puis transmet le choix de l'utilisateur
        avec l'entête `INBOX_READING_CHOICE`.

        Affiche le courriel à l'aide du gabarit `EMAIL_DISPLAY`.

        S'il n'y a pas de courriel à lire, l'utilisateur est averti avant de
        retourner au menu principal.
        """
        message = gloutils.GloMessage(
            header=gloutils.Headers.INBOX_READING_REQUEST,
            payload=None,
        )
        message_data = json.dumps(message)
        self._try_send_mesg(self._client_soc, message_data)

        reply_data = glosocket.recv_mesg(self._client_soc)
        reply  : gloutils.GloMessage = json.loads(reply_data)

        if reply["header"] == gloutils.Headers.OK:
            list_email : list[str] = reply["payload"]["email_list"]
            amount_emails = len(list_email)

            for email in list_email:
                print(email) # affiche les emails 

            if amount_emails > 0:
                good_choix = False
                while(not good_choix): # loop pour avoir un digit valide
                    choix = input(f"Entrez votre choix [1-{amount_emails}] : ")
                    if re.search(r"^[0-9]{1,10}$", choix):
                        choix_int = int(choix)
                        if choix_int <= amount_emails and choix_int >= 1:
                            good_choix = True
                    if not good_choix:
                        print("Choix invalide")
            
                # request pour avoir le email specifie
                message = gloutils.GloMessage(
                header=gloutils.Headers.INBOX_READING_CHOICE,
                    payload=gloutils.EmailChoicePayload(
                        choice=choix_int
                    ),
                )
                message_data = json.dumps(message)
                self._try_send_mesg(self._client_soc, message_data)

                reply_data = glosocket.recv_mesg(self._client_soc)
                reply  : gloutils.GloMessage = json.loads(reply_data)

                if reply["header"] == gloutils.Headers.OK: # received the body of the email
                    reply_payload : gloutils.EmailContentPayload = reply["payload"]

                    print(gloutils.EMAIL_DISPLAY.format(
                        sender=reply_payload["sender"],
                        to=reply_payload["destination"],
                        subject=reply_payload["subject"],
                        date=reply_payload["date"],
                        body=reply_payload["content"]
                    ))
                

    def _send_email(self) -> None:
        """
        Demande à l'utilisateur respectivement:
        - l'adresse email du destinataire,
        - le sujet du message,
        - le corps du message.

        La saisie du corps se termine par un point seul sur une ligne.

        Transmet ces informations avec l'entête `EMAIL_SENDING`.
        """
        destinataire = input("Entrez l'adresse du destinataire: ")
        sujet = input("Entrez le sujet: ")
        print("Entrez le contenu du courriel, terminez la saisie avec un '.' seul sur une ligne:")
        contenu = ""
        buffer = ""
        while buffer != ".\n":
            contenu += buffer
            buffer = input() + "\n"
            
        message = gloutils.GloMessage(
            header=gloutils.Headers.EMAIL_SENDING,
            payload=gloutils.EmailContentPayload(
                sender=f"{self._username}@{gloutils.SERVER_DOMAIN}",
                destination=destinataire,
                subject=sujet,
                content=contenu,
                date=gloutils.get_current_utc_time(),
            )
        )
        message_data = json.dumps(message)
        self._try_send_mesg(self._client_soc, message_data)

        reply_data = glosocket.recv_mesg(self._client_soc)
        reply  : gloutils.GloMessage = json.loads(reply_data)

        if reply["header"] ==  gloutils.Headers.OK:
            print()
            print("Le message a été envoyé avec succès!")
            
        elif reply["header"] == gloutils.Headers.ERROR:
            payload : gloutils.ErrorPayload = reply['payload']
            print(payload["error_message"]) # affiche erreur

    def _check_stats(self) -> None:
        """
        Demande les statistiques au serveur avec l'entête `STATS_REQUEST`.

        Affiche les statistiques à l'aide du gabarit `STATS_DISPLAY`.
        """
        message = gloutils.GloMessage(
            header=gloutils.Headers.STATS_REQUEST,
            payload=None,
        )
        message_data = json.dumps(message)
        self._try_send_mesg(self._client_soc, message_data)

        reply_data = glosocket.recv_mesg(self._client_soc)
        reply  : gloutils.GloMessage = json.loads(reply_data)

        if reply["header"] == gloutils.Headers.OK:
            reply_payload : gloutils.StatsPayload = reply["payload"]
            print(gloutils.STATS_DISPLAY.format(
                count=reply_payload["count"],
                size=reply_payload["size"]
            ))

    def _logout(self) -> None:
        """
        Préviens le serveur avec l'entête `AUTH_LOGOUT`.

        Met à jour l'attribut `_username`.
        """
        message = gloutils.GloMessage(
            header=gloutils.Headers.AUTH_LOGOUT,
            payload=None,
        )
        message_data = json.dumps(message)
        self._try_send_mesg(self._client_soc, message_data)
        self._username = ""

    def _try_send_mesg(self, client_soc: socket.socket, message_data:str)-> None:
        try:
            glosocket.snd_mesg(client_soc, message_data)
        except glosocket.GLOSocketError:
            sys.exit("Lost connection with the server")

    def _menu_principal(self) -> bool:
        """
        Custom fonction privee pour encapsuler les actions sur le menu principal

        Retourne vrai si doit quitter l'application
        """
        print()
        print(gloutils.CLIENT_USE_CHOICE)
        user_input = input("Entrez votre choix [1-4]: ")
        
        if not re.search(r"^[1234]$", user_input): # choix non valide
            print("Choix invalide")
            return False # restart le loop

        user_input = int(user_input)

        if user_input == 1: # Consulter courriel
            self._read_email()
        elif user_input == 2: # Envoi courriel
            self._send_email()
        elif user_input == 3: # Consultation des stats
            self._check_stats()
        elif user_input == 4: # Deconnexion
            self._logout()
        return False

    def _main_menu(self) -> bool:
        """
        Custom fonction privee pour encapsuler les actions sur le main menu

        Retourne vrai si doit quitter l'application
        """
        print()
        print(gloutils.CLIENT_AUTH_CHOICE)
        user_input = input("Entrez votre choix [1-3]: ")
        
        if not re.search(r"^[123]$", user_input): # choix non valide
            print("Choix invalide")
            return False # restart le loop
        
        user_input = int(user_input)

        if user_input == 1: # Creer un compte
            self._register()
        elif user_input == 2: # Se connecter
            self._login()
        elif user_input == 3: # Quitter
            self._quit()
            return True # Find du loop
        
        return False

    def run(self) -> None:
        """Point d'entrée du client."""
        should_quit = False

        while not should_quit:
            if not self._username:
                # Authentication menu
                should_quit = self._main_menu()
            else:
                # Choice menu
                should_quit = self._menu_principal()


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--destination", action="store",
                        dest="dest", required=True,
                        help="Adresse IP/URL du serveur.")
    args = parser.parse_args(sys.argv[1:])
    client = Client(args.dest)
    client.run()
    return 0


if __name__ == '__main__':
    sys.exit(_main())
