def menu():
    menu_string = """

        IOS-XE Chatbot
        ___ ___  ____      __  _______    ____ _           _   _           _
       |_ _/ _ \/ ___|     \ \/ / ____|  / ___| |__   __ _| |_| |__   ___ | |_
        | | | | \___ \ _____\  /|  _|   | |   | '_ \ / _` | __| '_ \ / _ \| __|
        | | |_| |___) |_____/  \| |___  | |___| | | | (_| | |_| |_) | (_) | |_
       |___\___/|____/     /_/\_\_____|  \____|_| |_|\__,_|\__|_.__/ \___/ \__|

        Operator Command Menu:

        /command - run a command directly on the device
        /menu    - print this menu
        /new     - start a new context window
        /prompt  - print the developer prompt
        /quit    - quit the program


        To interact with the LMM just type you query.

        """

    print(menu_string)
