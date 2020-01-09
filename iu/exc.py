class OrderValidationError(ValueError):
    pass


class NotEnoughBalance(OrderValidationError):
    pass
