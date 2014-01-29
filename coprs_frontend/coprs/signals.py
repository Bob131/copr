import blinker

coprs_signals = blinker.Namespace()

build_finished = coprs_signals.signal("build-finished")
copr_created = coprs_signals.signal("copr-created")
