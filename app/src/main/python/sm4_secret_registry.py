"""Authoritative SM4 candidate registry for ALVSIA PRO 4.7 modders."""
SM4_SECRET_NEW_VERSION = "4.7-modders"
SM4_SECRET_NEW_EXPECTED_COUNT = 23
SM4_SECRET_NEW = (
    "xG2qW5lP7lV2iN5fN5pG",
    "xT1cJ6dL5wC0kK1rB4dK",
    "qC4jS5bZ6fL5xE6nD4zA",
    "gD4jQ2aL3bS3lC3xT0iW",
    "xU1yQ8wE9zY3gZ3bT5aE",
    "uQ3cO2dX7xY4xU7gH7iS",
    "gW1fR0jK6wQ4oN0oK1kZ",
    "aJ4pV7iZ7pU4wP2aC2cZ",
    "cX6jT3cM2oT3vK0kJ1qN",
    "iT2vS0cS6yT6cZ1sE1lO",
    "hM1pH9iY8wM9hT4lN5uJ",
    "kG6bC8jK0fL0dE4sH4mL",
    "dB6lB3vE0eZ8wM8rI0aC",
    "tP7sP7nI9rA2vQ4cV5yQ",
    "aT0cL1yN4pT3sZ7eM2vY",
    "uV6fU8fC9zN3mP5dH8mN",
    "rT6aQ6oZ1yM0gO5tO1aN",
    "jU5bH7lQ0fM9hK2kI0oF",
    "iQ0eM0mJ7uT0kV6kL5zY",
    "rG0lR2rZ5vM6mW5lM1rR",
    "wD2rP3lP9xF4mE1eC5jS",
    "fO3kW1fE6eD0pU1kY7xK",
    "nE1jQ6qK5tW7rM8iD5vV",
)
SM4_SECRET_NEW_SET = frozenset(SM4_SECRET_NEW)


def validate_sm4_secret_set() -> dict:
    valid = (
        len(SM4_SECRET_NEW) == SM4_SECRET_NEW_EXPECTED_COUNT == 23
        and len(SM4_SECRET_NEW_SET) == 23
        and all(isinstance(key, str) and len(key) == 20 for key in SM4_SECRET_NEW)
    )
    return {
        "ok": valid,
        "version": SM4_SECRET_NEW_VERSION,
        "count": len(SM4_SECRET_NEW),
        "expected_count": SM4_SECRET_NEW_EXPECTED_COUNT,
    }
