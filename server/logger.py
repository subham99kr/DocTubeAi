import logging

def setup_logger(name="DocTubeAI"):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    #console_handler = logging.StreamHandler()
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    #formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)

    # add the handlers to the logger...because python would also shows duplicate logs otherwise
    if not logger.hasHandlers():
        logger.addHandler(ch)    

    return logger


logger = setup_logger()
