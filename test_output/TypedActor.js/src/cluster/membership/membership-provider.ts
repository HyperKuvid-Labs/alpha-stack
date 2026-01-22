import { ActorSystem } from '../../core/actor-system';

export abstract class MembershipProvider {
  public abstract join(system: ActorSystem): Promise<void>;
  public abstract leave(): Promise<void>;
  public abstract getMembers(): string[];
}
