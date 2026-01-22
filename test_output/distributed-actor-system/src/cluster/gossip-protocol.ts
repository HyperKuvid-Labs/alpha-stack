import { NodeManager } from './node-manager';
import { Transport } from '../remote/transport';
import { ActorAddress } from '../types/actor.types';
import { ClusterMember } from '../types/cluster.types';

export type GossipMessage = {
  type: 'GossipPayload';
  senderAddress: ActorAddress;
  members: ClusterMember[];
};

export class GossipProtocol {
  private readonly nodeManager: NodeManager;
  private readonly transport: Transport;
  private isRunning: boolean = false;
  private gossipIntervalMs: number;
  private gossipTimer?: NodeJS.Timeout;
  private readonly selfAddress: ActorAddress;

  constructor(
    nodeManager: NodeManager,
    transport: Transport,
    selfAddress: ActorAddress,
    gossipIntervalMs: number = 1000
  ) {
    this.nodeManager = nodeManager;
    this.transport = transport;
    this.selfAddress = selfAddress;
    this.gossipIntervalMs = gossipIntervalMs;
  }

  public async start(): Promise<void> {
    if (this.isRunning) {
      return;
    }
    this.isRunning = true;
    this.gossipTimer = setInterval(() => this.sendGossip(), this.gossipIntervalMs);
    this.transport.onMessage(this.handleIncomingMessage.bind(this));
  }

  public async stop(): Promise<void> {
    if (!this.isRunning) {
      return;
    }
    this.isRunning = false;
    if (this.gossipTimer) {
      clearInterval(this.gossipTimer);
      this.gossipTimer = undefined;
    }
    // Note: Transport currently lacks an offMessage method, assuming a single handler or internal cleanup.
    // For a robust implementation, `Transport` would need `offMessage`.
  }

  private async handleIncomingMessage(senderAddress: ActorAddress, message: any): Promise<void> {
    if (message && message.type === 'GossipPayload') {
      const gossipMessage = message as GossipMessage;
      // This assumes NodeManager has a public method `mergeClusterState` to update its view.
      // This method is critical for the gossip protocol's functionality.
      await this.nodeManager.mergeClusterState(gossipMessage.members);
    }
  }

  private async sendGossip(): Promise<void> {
    if (!this.isRunning) {
      return;
    }

    const currentMembers = this.nodeManager.getMembers();
    const potentialRecipients = currentMembers.filter(
      member => member.address.host !== this.selfAddress.host || member.address.port !== this.selfAddress.port
    );

    if (potentialRecipients.length === 0) {
      return;
    }

    const randomIndex = Math.floor(Math.random() * potentialRecipients.length);
    const targetMember = potentialRecipients[randomIndex];

    const gossipPayload: GossipMessage = {
      type: 'GossipPayload',
      senderAddress: this.selfAddress,
      members: currentMembers,
    };

    try {
      await this.transport.send(targetMember.address, gossipPayload);
    } catch (error) {
      // In a real system, more sophisticated error handling (e.g., marking node as suspect)
      // and logging would be implemented here.
    }
  }
}
