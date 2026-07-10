"""Constants for the Helios easyControls 3.0 integration."""

DOMAIN = "helios_easycontrol3"

CONF_HOST = "host"

DEFAULT_PORT = 80
DEFAULT_SCAN_INTERVAL_SECONDS = 60
DEFAULT_REQUEST_TIMEOUT_SECONDS = 10
DEFAULT_OFFLINE_AFTER_MINUTES = 10

# Minimum spacing between two writes to the device. The KWL's embedded
# webserver copes badly with bursts of connections/writes (rapid mode
# switching could physically reset the unit). Writes arriving faster are
# accepted immediately by HA, coalesced per channel (latest wins) and
# sent once the interval allows. See coordinator.queue_write().
WRITE_MIN_INTERVAL_SECONDS = 2.0
