# TODO: Implement dump the current context window
def menu():
    menu_string = """

        IOS-XE Chatbot
        ___ ___  ____      __  _______    ____ _           _   _           _
       |_ _/ _ \/ ___|     \ \/ / ____|  / ___| |__   __ _| |_| |__   ___ | |_
        | | | | \___ \ _____\  /|  _|   | |   | '_ \ / _` | __| '_ \ / _ \| __|
        | | |_| |___) |_____/  \| |___  | |___| | | | (_| | |_| |_) | (_) | |_
       |___\___/|____/     /_/\_\_____|  \____|_| |_|\__,_|\__|_.__/ \___/ \__|

        Operator Command Menu:

        /c  - run a command directly on the device
        /m  - print this menu
        /n  - start a new context window
        /p  - print the developer prompt
        /r  - reload the developer prompt
        /q  - quit the program1


        To interact with the LMM just type you query.

        """

    print(menu_string)
