from shema_platform.experience.api import create_app
from shema_platform.experience.runtime_application import (
    ProviderNeutralRuntimeApplication,
)

app = create_app(
    application=ProviderNeutralRuntimeApplication(),
    enable_docs=False,
)
