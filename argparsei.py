import argparse

class InteractiveArgumentParser(argparse.ArgumentParser):
    def exit(self, status=0, message=None):
        if message:
            raise argparse.ArgumentError(argument=None, message=message)