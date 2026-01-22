import { ActorAddress, ClusterMember, ClusterMemberStatus } from '../types/cluster.types';
import { ActorSystem } from '../core/actor-system';
import { Transport } from '../remote/transport';
import { GossipProtocol } from './gossip-protocol';

export class NodeManager {
    private _system: ActorSystem;
    private _transport: Transport;
    private _gossipProtocol: GossipProtocol | null = null;
    private _localAddress: ActorAddress;
    private _members: Map<string, ClusterMember> = new Map();
    private _isJoined: boolean = false;

    constructor(system: ActorSystem, transport: Transport, localAddress: ActorAddress) {
        this._system = system;
        this._transport = transport;
        this._localAddress = localAddress;

        this._members.set(this._localAddress.path, {
            address: this._localAddress,
            status: ClusterMemberStatus.Joining,
            roles: [],
            upNumber: 0,
        });
    }

    public setGossipProtocol(gossip: GossipProtocol): void {
        this._gossipProtocol = gossip;
    }

    public async join(seedNodes: ActorAddress[]): Promise<void> {
        if (this._isJoined) {
            return;
        }

        console.log(`Node ${this._localAddress.host}:${this._localAddress.port}/${this._localAddress.path} attempting to join cluster via seed nodes:`, seedNodes.map(s => s.host + ':' + s.port));

        let successfullyContactedSeed = false;
        for (const seedAddress of seedNodes) {
            try {
                const joinRequest = {
                    type: 'NodeJoinRequest',
                    sender: this._localAddress,
                    systemName: this._system.name
                };
                // Simulate sending a join request and receiving initial cluster state
                // In a real implementation, this would involve remote communication via `_transport`
                // and receiving a list of known cluster members from the seed node.
                // For now, we simulate success and add the seed node itself to our members.
                const initialMembers: ClusterMember[] = [
                    { address: seedAddress, status: ClusterMemberStatus.Up, roles: [], upNumber: 1 },
                ];

                for (const member of initialMembers) {
                    this._members.set(member.address.path, member);
                }
                successfullyContactedSeed = true;
                break;
            } catch (error) {
                console.error(`Failed to contact seed node ${seedAddress.host}:${seedAddress.port}: ${error}`);
            }
        }

        if (!successfullyContactedSeed && seedNodes.length > 0) {
            throw new Error(`Failed to join cluster: Could not connect to any provided seed nodes.`);
        }

        const localMember = this._members.get(this._localAddress.path);
        if (localMember) {
            localMember.status = ClusterMemberStatus.Up;
            localMember.upNumber = (localMember.upNumber || 0) + 1;
            this._members.set(this._localAddress.path, localMember);
        }

        this._isJoined = true;
        console.log(`Node ${this._localAddress.host}:${this._localAddress.port}/${this._localAddress.path} successfully joined the cluster.`);

        if (this._gossipProtocol) {
            await this._gossipProtocol.start();
        } else {
            console.warn('Gossip protocol not configured. Cluster state may not be eventually consistent.');
        }
    }

    public async leave(): Promise<void> {
        if (!this._isJoined) {
            return;
        }

        console.log(`Node ${this._localAddress.host}:${this._localAddress.port}/${this._localAddress.path} is gracefully leaving the cluster.`);

        if (this._gossipProtocol) {
            await this._gossipProtocol.stop();
        }

        const localMember = this._members.get(this._localAddress.path);
        if (localMember) {
            localMember.status = ClusterMemberStatus.Leaving;
            localMember.upNumber = (localMember.upNumber || 0) + 1;
            this._members.set(this._localAddress.path, localMember);
        }

        this._members.clear();
        this._isJoined = false;
        console.log(`Node ${this._localAddress.host}:${this._localAddress.port}/${this._localAddress.path} has left the cluster.`);
    }

    public getMembers(): ClusterMember[] {
        return Array.from(this._members.values());
    }

    public updateMember(member: ClusterMember): void {
        const existingMember = this._members.get(member.address.path);

        if (!existingMember || member.upNumber > (existingMember.upNumber || 0) || member.status > existingMember.status) {
            this._members.set(member.address.path, member);
        }
    }

    public removeMember(address: ActorAddress): void {
        if (this._members.has(address.path)) {
            this._members.delete(address.path);
            console.log(`NodeManager: Member removed - ${address.path}`);
        }
    }

    public mergeClusterState(incomingState: Map<string, ClusterMember>): void {
        for (const [addressPath, incomingMember] of incomingState.entries()) {
            const existingMember = this._members.get(addressPath);

            if (!existingMember) {
                this._members.set(addressPath, incomingMember);
                console.log(`NodeManager: Added new member ${addressPath}`);
            } else if (incomingMember.upNumber > existingMember.upNumber ||
                       (incomingMember.upNumber === existingMember.upNumber && incomingMember.status > existingMember.status)) {
                this._members.set(addressPath, incomingMember);
                console.log(`NodeManager: Updated member ${addressPath} to new state`);
            }
        }
    }

    public get localAddress(): ActorAddress {
        return this._localAddress;
    }
}
