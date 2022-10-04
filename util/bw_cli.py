#!/usr/bin/env python3
# extremely simple bitwarden cli wrapper
# Author: @jessebot jessebot@linux.com
"""
Example:
        bw = BwCLI()
        bw.unlock()
        bw.generate()
        bw.create_login(name="test mctest",
                        item_url="coolhosting4dogs.tech",
                        user="admin",
                        password="fakepassword")
        bw.lock()
"""
import base64
import json
from getpass import getpass
from .subproc_wrapper import subproc
from .logging import header


class BwCLI():
    """
    Python Wrapper for the Bitwarden cli
    """
    def __init__(self,):
        """
        This is mostly for storing the session
        """
        self.session = None

    def generate(self, special_characters=False):
        """
        generate a new password. Takes special_characters bool.
        """
        header('Generating a new password...')

        command = "bw generate --length 24 --uppercase --lowercase --number"
        if special_characters:
            command += " --special"

        password = subproc([command])
        return password

    def unlock(self):
        """
        unlocks the local bitwarden vault, and returns session token
        TODO: check local env vars for password or api key
        """
        header('Unlocking the Bitwarden vault...')

        password_prompt = 'Enter your Bitwarden Password: '
        password = getpass(prompt=password_prompt, stream=None)

        self.session = subproc([f"bw unlock {password} --raw"], False, True)

    def lock(self):
        """
        lock the local bitwarden vault
        """
        header('Locking the Bitwarden vault...')
        subproc([f"bw lock --session {self.session}"])
        return

    def create_login(self, name="", item_url="", user="", password="",
                     org=None, collection=None):
        """
        Create login items, and only login items
        takes optional organization and collection
        """
        header('Creating bitwarden login item...')
        login_obj = json.dumps({
            "organizationId": org,
            "collectionIds": collection,
            "folderId": None,
            "type": 1,
            "name": item_url,
            "notes": None,
            "favorite": False,
            "fields": [],
            "login": {"uris": [{"match": 0,
                                "uri": item_url}],
                      "username": user,
                      "password": password,
                      "totp": None},
            "secureNote": None,
            "card": None,
            "identity": None,
            "reprompt": 0})

        encodedBytes = base64.b64encode(login_obj.encode("utf-8"))
        encodedStr = str(encodedBytes, "utf-8")

        subproc([f"bw create item {encodedStr} --session {self.session}"])
