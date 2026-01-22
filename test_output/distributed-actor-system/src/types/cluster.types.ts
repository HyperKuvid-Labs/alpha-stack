import { ActorAddress, ActorProps } from './actor.types';
import { ActorSystem } from '../core/actor-system';

export interface ClusterMember {
  id: string;
  address: ActorAddress;
  status: ClusterMemberStatus;
  upTimestamp: number;
}

export type ClusterMemberStatus =
  | 'Joining'
  | 'Up'
  | 'Leaving'
  | 'Down';

export interface ClusterState {
  members: ClusterMember[];
  leader?: string;
  version: number;
}

export interface ShardingOptions {
  typeName: string;
  entityProps: ActorProps<any>;
  extractEntityId: (message: object) => string;
  extractShardId: (entityId: string) => string;
  numberOfShards: number;
  role?: string;
  rebalanceIntervalMs?: number;
}
