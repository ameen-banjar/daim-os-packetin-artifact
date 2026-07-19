# Real OpenFlow controller protocol

Os-Ken 2.6.0 runs `osken_learning_controller.py` with OpenFlow 1.3. Mininet
switches use `RemoteController` at 127.0.0.1:6653. The experiment must record
`ovs-vsctl get-controller`, `ovs-vsctl get bridge protocols`, and controller
stdout before the process is stopped. A result is valid only when every switch
has an established controller connection before fault injection.
