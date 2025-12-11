if __name__ == "__main__":
    from zulu.module_helper import preimport_modules
    preimport_modules("./", accept_patterns = [r"^processors_", r"^pipelines"])
    import process
