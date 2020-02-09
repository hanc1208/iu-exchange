docker stop blockchain-bitcoin
docker rm blockchain-bitcoin
docker run -d \
           -v blockchain-bitcoin:/bitcoin \
           --name blockchain-bitcoin \
           -p 127.0.0.1:8332:8332 \
           kylemanna/bitcoind \
           -prune=550 \
           -disablewallet \
           -rest \
           -rpcallowip=172.17.0.1 \
           -rpcuser=iu-exchange \
           -rpcpassword= \
           -dbcache=1024
docker stop blockchain-bitcoin-testnet
docker rm blockchain-bitcoin-testnet
docker run -d \
           -v blockchain-bitcoin-testnet:/bitcoin \
           --name blockchain-bitcoin-testnet \
           -p 127.0.0.1:18332:18332 \
           kylemanna/bitcoind \
           -testnet \
           -prune=550 \
           -disablewallet \
           -rest \
           -rpcallowip=172.17.0.1 \
           -rpcuser=iu-exchange \
           -rpcpassword=
