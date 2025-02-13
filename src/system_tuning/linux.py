import resource

def set_max_open_file_descriptors(new_limit):
    # Get the current limits
    soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)

    # Set the new limit for the current process
    if new_limit > hard_limit:
        raise Exception("Error: The new limit exceeds the hard limit.")

    resource.setrlimit(resource.RLIMIT_NOFILE, (new_limit, hard_limit))
