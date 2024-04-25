# Delegated Proof of Authority with Downgrade consensus algorithm

SINTEF has developed a Delegated Proof of Authority (DDPoA) consensus algorithm that aims to perform well under unstable
networks within the confinements of the Hyperledger sawtooth framework.
The algorithm is simple plug-n-play and you can simply reference the docker image into your sawtooth application and it
will work. The paper detailing the implementation is under progress.

## The key points for DDPoA

- Fast
-
    - Entire network knows which node should produce the next block at any time
-
    - Voting is done in parallel with block production – no idle time
-
    - Downgrade mechanism minimizes the negative impact malicious and slow nodes have on the network throughput

- Configurable / Dynamic
-
    - Number of block producers
-
    - Delegates (not all nodes have to be candidates)
-
    - Rounds per epoch (how many times the same witness list is re-used before a new election)
-
    - Slot duration (block interval)

## Evaluation

We have currently evaluated the consensus algorithms by utilizing the intkey transaction family, where each runs used an
identical seed to create reproducible runs, so that all comparisons can be evaluated and compared without bias. Each
parameter configuration for the consensus evaluation was ran 3 three times consisting of 10 minutes run, and the results
were averaged with eventual outliers removed. As a prerequisite to the performance testing, we created a set of
integration tests to determine whether the system was fault tolerant and would pass the liveness test.
Running `make run` will spin up 4 consensus nodes (and validators and settings-tps) using docker-compose.

During these integration tests we discovered a fatal problem for the Intel designed POET consensus algorithm. It forks,
without proper resolutions for TPS > 5, and has therefore been excluded from the final results until we can create a
simplified test or do some custom tweaking to the network. Once forked, it does not pass liveness test(s) and the
network is broken. Therefore, this initial preliminary test will only show the results from PBFT and DDPoA.
All test followed the same initial 4 steps:

1. Create a Kubernetes description for the given run
2. Initialize the YAML file
3. Process and send the workload to the newly created network
4. Scale down and collect metrics from the InfluxDB

During the testing we saw that DDPoA was a order of magnitude faster than PBFT, and all simulation (including with
varying network latency) and testing is
indicative of much poorer results for PBFT and better for DDPoA, which is why we had to perform code analysis on the
Sawtooth framework in order to explain the results. We did not think POET would function so badly in a real life
environment, not being able to recover from forks in larger networks. Further testing showed that all networks face a
large backpressure (queued transactions) from the validators which results in a QUEUE_FULL FLAGS, and this happens very
fast because Sawtooth shares a single message queue for all types of messages, from transaction processors to consensus
messages. Since DDPoA and POET relies on message passing for its algorithms, the algorithms will not receive its
consensus agreement within the scope of an epoch, which furthermore propagates the error. This happens because missed
slots and epochs, requires another consensus round, which furthermore causes more messages. Since messages are dropped
with a full message queue, the message-based protocols struggle within the confinement of Sawtooth.
The poor performance of both working consensus algorithms should normally plateau either within CPU bounds or maximum
network capacity, however we observe that we are limited by the overhead invoked by a full transaction queue; when a
Sawtooth validator’s transactions queue is full, all subsequent transaction are dropped but responded to with a ack and
QUEUE_FULL response which consumes resources and time normally spent in the validation process. Since PBFT does not do
lottery nor any ‘rounds’ of transaction, it functions best within these poor restrictions.
Therefore, we are developing a DDPoA v2 which uses an overlay network for consensus messages, relying less on the
internal sawtooth message queue. This would allow us to bypass the poor design choices of the shared queue.

## Running

Simply plug the consensus image into your application and it will work. To test the network with our configuration(s)
please use the start.sh and stop.sh file to run the regular docker compose file. For Kubernetes please apply the
following provisions: 


kubectl apply -f config/influxdb-pv.yaml

kubectl apply -f config/influxdb-pvc.yaml

kubectl apply -f config/grafana-provision.yaml

Then run the kubernetes_test_file.yml

### Happy hacking!