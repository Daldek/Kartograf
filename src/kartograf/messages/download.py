"""Messages of the downloads (``kartograf.download``): the update plan."""

from kartograf.messages import Text

MESSAGES = {
    # ``download``: a plan file from before the store key became ``root`` (0.8.0-dev).
    "old_plan_store_key": Text(
        "The plan has the key store of 0.8.0-dev, which is now root: make a new plan "
        "with --check",
        "Plan ma klucz store z 0.8.0-dev, ktory nazywa sie teraz root: zrob nowy plan "
        "z --check",
    ),
}
