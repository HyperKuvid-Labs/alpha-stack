import { describe, it, expect, beforeEach, fn } from 'bun:test';
import { NodeManager } from './node-manager';
import type { ActorSystem } from '../core/actor-system';
import type { Transport } from '../remote/transport';
import type { GossipProtocol } from './gossip-protocol';
import { ActorAddress } from '../core/actor-ref';
import { ClusterMember, ClusterMemberStatus } from '../types/cluster.types';
import type { WelcomeMessage } from '../types/message.types';

const mockActorSystem = {
  tell: fn(),
  ask: fn(),
  actorOf: fn(),
  path: 'local-system',
  register: fn(),
} as unknown as jest.Mocked<ActorSystem>;

const mockTransport = {
  start: fn().mockResolvedValue(undefined),
  stop: fn().mockResolvedValue(undefined),
  send: fn().mockResolvedValue(undefined),
} as unknown as jest.Mocked<Transport>;

const mockGossipProtocol = {
  start: fn(),
  stop: fn(),
} as unknown as jest.Mocked<GossipProtocol>;


const createActorAddress = (host: string, port: number, system: string = 'test-system') => {
  return ActorAddress.fromString(`actor://${system}@${host}:${port}/user/node`);
};

const createClusterMember = (address: ActorAddress, status: ClusterMemberStatus): ClusterMember => ({
  address,
  status,
  joinedAt: Date.now(),
});

describe('NodeManager', () => {
  let localAddress: ActorAddress;
  let nodeManager: NodeManager;

  beforeEach(() => {
    mockActorSystem.ask.mockClear();
    mockActorSystem.tell.mockClear();
    mockTransport.send.mockClear();
    mockTransport.stop.mockClear();
    mockGossipProtocol.start.mockClear();
    mockGossipProtocol.stop.mockClear();

    localAddress = createActorAddress('127.0.0.1', 8000);
    nodeManager = new NodeManager(mockActorSystem, mockTransport, localAddress);
    nodeManager.setGossipProtocol(mockGossipProtocol);
  });

  it('should initialize with the local node in the member list with Joining status', () => {
    const members = nodeManager.getMembers();
    expect(members).toHaveLength(1);
    expect(members[0].address.toString()).toBe(localAddress.toString());
    expect(members[0].status).toBe(ClusterMemberStatus.Joining);
    expect(nodeManager.localAddress).toBe(localAddress);
  });

  describe('updateMember', () => {
    it('should add a new member to the list', () => {
      const newMemberAddress = createActorAddress('127.0.0.1', 8001);
      const newMember = createClusterMember(newMemberAddress, ClusterMemberStatus.Up);
      nodeManager.updateMember(newMember);

      const members = nodeManager.getMembers();
      expect(members).toHaveLength(2);
      expect(members.find(m => m.address.equals(newMemberAddress))).toBeDefined();
    });

    it('should update the status of an existing member', () => {
      const newMemberAddress = createActorAddress('127.0.0.1', 8001);
      const joiningMember = createClusterMember(newMemberAddress, ClusterMemberStatus.Joining);
      nodeManager.updateMember(joiningMember);
      expect(nodeManager.getMembers().find(m => m.address.equals(newMemberAddress))?.status).toBe(ClusterMemberStatus.Joining);

      const upMember = createClusterMember(newMemberAddress, ClusterMemberStatus.Up);
      nodeManager.updateMember(upMember);
      const members = nodeManager.getMembers();
      expect(members).toHaveLength(2);
      expect(members.find(m => m.address.equals(newMemberAddress))?.status).toBe(ClusterMemberStatus.Up);
    });

    it('should not add a duplicate member', () => {
      const newMemberAddress = createActorAddress('127.0.0.1', 8001);
      const newMember = createClusterMember(newMemberAddress, ClusterMemberStatus.Up);
      nodeManager.updateMember(newMember);
      nodeManager.updateMember(newMember);

      expect(nodeManager.getMembers()).toHaveLength(2);
    });
  });

  describe('removeMember', () => {
    it('should remove an existing member from the list', () => {
      const memberAddressToRemove = createActorAddress('127.0.0.1', 8001);
      const memberToRemove = createClusterMember(memberAddressToRemove, ClusterMemberStatus.Up);
      nodeManager.updateMember(memberToRemove);
      expect(nodeManager.getMembers()).toHaveLength(2);

      nodeManager.removeMember(memberAddressToRemove);
      const members = nodeManager.getMembers();
      expect(members).toHaveLength(1);
      expect(members.find(m => m.address.equals(memberAddressToRemove))).toBeUndefined();
    });

    it('should do nothing if the member to remove does not exist', () => {
      const nonExistentAddress = createActorAddress('127.0.0.1', 9999);
      const initialMembers = [...nodeManager.getMembers()];
      nodeManager.removeMember(nonExistentAddress);
      expect(nodeManager.getMembers()).toEqual(initialMembers);
    });

    it('should not allow removing the local node', () => {
        nodeManager.removeMember(localAddress);
        expect(nodeManager.getMembers()).toHaveLength(1);
        expect(nodeManager.getMembers()[0].address.equals(localAddress)).toBe(true);
    });
  });

  describe('join', () => {
    const seedNode1 = createActorAddress('127.0.0.1', 7000);
    const seedNode2 = createActorAddress('127.0.0.1', 7001);

    it('should successfully join a cluster via a seed node', async () => {
      const existingMemberAddress = createActorAddress('10.0.0.1', 8080);
      const existingMember = createClusterMember(existingMemberAddress, ClusterMemberStatus.Up);
      const welcomeMessage: WelcomeMessage = {
        type: 'Welcome',
        members: [existingMember],
      };

      mockActorSystem.ask.mockResolvedValue(welcomeMessage);

      await nodeManager.join([seedNode1]);

      const members = nodeManager.getMembers();
      expect(members).toHaveLength(2);
      expect(members.find(m => m.address.equals(existingMemberAddress))).toBeDefined();

      const localMember = members.find(m => m.address.equals(localAddress));
      expect(localMember?.status).toBe(ClusterMemberStatus.Up);

      expect(mockActorSystem.ask).toHaveBeenCalledTimes(1);
      const [target, message] = mockActorSystem.ask.mock.calls[0];
      expect(target.toString()).toBe(seedNode1.toString());
      expect(message.type).toBe('Join');

      expect(mockGossipProtocol.start).toHaveBeenCalledTimes(1);
    });

    it('should become the first node if no seed nodes are provided', async () => {
      await nodeManager.join([]);

      const members = nodeManager.getMembers();
      expect(members).toHaveLength(1);
      const localMember = members.find(m => m.address.equals(localAddress));
      expect(localMember?.status).toBe(ClusterMemberStatus.Up);

      expect(mockActorSystem.ask).not.toHaveBeenCalled();
      expect(mockGossipProtocol.start).toHaveBeenCalledTimes(1);
    });

    it('should try the next seed node if the first one fails', async () => {
        const existingMemberAddress = createActorAddress('10.0.0.1', 8080);
        const existingMember = createClusterMember(existingMemberAddress, ClusterMemberStatus.Up);
        const welcomeMessage: WelcomeMessage = {
          type: 'Welcome',
          members: [existingMember],
        };

        mockActorSystem.ask
            .mockRejectedValueOnce(new Error('Connection failed'))
            .mockResolvedValueOnce(welcomeMessage);

        await nodeManager.join([seedNode1, seedNode2]);

        expect(mockActorSystem.ask).toHaveBeenCalledTimes(2);
        expect(mockActorSystem.ask.mock.calls[0][0].toString()).toBe(seedNode1.toString());
        expect(mockActorSystem.ask.mock.calls[1][0].toString()).toBe(seedNode2.toString());

        const localMember = nodeManager.getMembers().find(m => m.address.equals(localAddress));
        expect(localMember?.status).toBe(ClusterMemberStatus.Up);
        expect(mockGossipProtocol.start).toHaveBeenCalledTimes(1);
    });

    it('should throw an error if all seed nodes fail', async () => {
      mockActorSystem.ask.mockRejectedValue(new Error('Connection failed'));

      await expect(nodeManager.join([seedNode1, seedNode2])).rejects.toThrow('Could not join cluster. All seed nodes failed.');

      const localMember = nodeManager.getMembers().find(m => m.address.equals(localAddress));
      expect(localMember?.status).toBe(ClusterMemberStatus.Joining);
      expect(mockGossipProtocol.start).not.toHaveBeenCalled();
    });
  });

  describe('leave', () => {
    it('should gracefully leave the cluster', async () => {
      const otherMemberAddress = createActorAddress('127.0.0.1', 8001);
      const otherMember = createClusterMember(otherMemberAddress, ClusterMemberStatus.Up);
      nodeManager.updateMember(otherMember);
      nodeManager.updateMember({ ...nodeManager.getMembers()[0], status: ClusterMemberStatus.Up });

      await nodeManager.leave();

      const localMember = nodeManager.getMembers().find(m => m.address.equals(localAddress));
      expect(localMember?.status).toBe(ClusterMemberStatus.Down);

      expect(mockGossipProtocol.stop).toHaveBeenCalledTimes(1);
      expect(mockTransport.stop).toHaveBeenCalledTimes(1);
    });
  });
});
