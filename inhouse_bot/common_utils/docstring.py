def doc(docstring):
    def document(func):
        func.__doc__ = docstring
        return func

    return document