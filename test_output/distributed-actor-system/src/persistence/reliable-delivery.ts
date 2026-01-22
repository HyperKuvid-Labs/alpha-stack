typescript
import { Actor, ActorContext } from '../core/actor';
import { ActorRef } from '../core/actor-ref';
import { ActorSystem } from '../core/actor-system';
import { Receive } from '../core/decorators';
import { Journal, EventEnvelope } from './journal';
import { ActorAddress } from '../types/actor.types';
import { Message, SystemMessage } from '../types/message.types';

export interface ReliableEnvelope<T extends Message> {
  readonly __isReliableDelivery: true;
  readonly deliveryId: string;
  readonly senderAddress: ActorAddress | null;
  readonly originalMessage: T;
}

export class DeliveryConfirmation implements SystemMessage {
  readonly __isSystemMessage = true;
  constructor(
    public readonly deliveryId: string,
    public readonly recipientAddress: ActorAddress
  ) {}
}

export class OutboundMessageState {
  constructor(
    public readonly deliveryId: string,
    public readonly recipient: ActorAddress,
    public readonly message: Message,
    public readonly sender: ActorRef<any> | null,
    public readonly timestamp: number,
    public retryCount: number = 0
  ) {}
}

export class OutboundMessageSentEvent {
  readonly type = 'OutboundMessageSent';
  constructor(public readonly state: OutboundMessageState) {}
}

export class MessageConfirmedEvent {
  readonly type = 'MessageConfirmed';
  constructor(public readonly deliveryId: string, public readonly recipientAddress: ActorAddress) {}
}

export type ReliableDeliveryEvent = OutboundMessageSentEvent | MessageConfirmedEvent;

export interface ReliableDeliveryConfig {
  retryIntervalMs: number;
  maxRetries: number;
  deadLetterActorPath?: string;
}

export class ReliableDelivery {
  private static RELIABLE_DELIVERY_PID = "reliable-delivery-outbox";

  private readonly system: ActorSystem;
  private readonly journal: Journal;
  private readonly config: ReliableDeliveryConfig;

  private outbox: Map<string, OutboundMessageState> = new Map();

  private retryTimer: Timer | null = null;
  private confirmationActorRef: ActorRef<DeliveryConfirmation | SetReliableDeliveryRef | StopConfirmationActor>;

  private constructor(system: ActorSystem, journal: Journal, config: ReliableDeliveryConfig, confirmationActorRef: ActorRef<DeliveryConfirmation | SetReliableDeliveryRef | StopConfirmationActor>) {
    this.system = system;
    this.journal = journal;
    this.config = config;
    this.confirmationActorRef = confirmationActorRef;
  }

  public static async create(system: ActorSystem, journal: Journal, config: ReliableDeliveryConfig): Promise<ReliableDelivery> {
    const confirmationActorRef = system.actorOf({
      actorClass: ReliableDeliveryConfirmationActor,
      args: [],
    }, "reliable-delivery-confirmation-actor");

    const delivery = new ReliableDelivery(system, journal, config, confirmationActorRef);

    await confirmationActorRef.ask(new SetReliableDeliveryRef(delivery));

    await delivery.recoverOutbox();
    delivery.startRetries();
    return delivery;
  }

  public async send<T extends Message>(target: ActorRef<T>, message: T, sender: ActorRef<any> | null = null): Promise<void> {
    const deliveryId = this.system.generateUniqueId();
    const state = new OutboundMessageState(deliveryId, target.address, message, sender, Date.now());

    await this.journal.writeEvents([
      this.createEventEnvelope(OutboundMessageSentEvent, { state })
    ]);

    this.outbox.set(deliveryId, state);
    this.sendOnce(state);
  }

  public async confirmMessage(deliveryId: string, recipientAddress: ActorAddress): Promise<void> {
    if (this.outbox.has(deliveryId)) {
      await this.journal.writeEvents([
        this.createEventEnvelope(MessageConfirmedEvent, { deliveryId, recipientAddress })
      ]);
      this.outbox.delete(deliveryId);
    }
  }

  public async stop(): Promise<void> {
    if (this.retryTimer) {
      clearInterval(this.retryTimer);
      this.retryTimer = null;
    }
    await this.confirmationActorRef.ask(new StopConfirmationActor());
  }

  private createEventEnvelope<T extends new (...args: any[]) => ReliableDeliveryEvent>(EventType: T, payload: ConstructorParameters<T>[0]): EventEnvelope<ReliableDeliveryEvent> {
    return {
      persistenceId: ReliableDelivery.RELIABLE_DELIVERY_PID,
      sequenceNr: -1,
      timestamp: Date.now(),
      event: new EventType(payload),
    };
  }

  private async recoverOutbox(): Promise<void> {
    const events = this.journal.replayEvents<ReliableDeliveryEvent>(ReliableDelivery.RELIABLE_DELIVERY_PID, 0);
    const tempOutbox: Map<string, OutboundMessageState> = new Map();

    for await (const envelope of events) {
      if (envelope.event.type === 'OutboundMessageSent') {
        tempOutbox.set(envelope.event.state.deliveryId, envelope.event.state);
      } else if (envelope.event.type === 'MessageConfirmed') {
        tempOutbox.delete(envelope.event.deliveryId);
      }
    }
    this.outbox = tempOutbox;
  }

  private startRetries(): void {
    if (this.retryTimer) {
      clearInterval(this.retryTimer);
    }
    this.retryTimer = setInterval(() => this.processOutbox(), this.config.retryIntervalMs);
  }

  private processOutbox(): void {
    for (const [deliveryId, state] of this.outbox.entries()) {
      if (state.retryCount >= this.config.maxRetries) {
        console.warn(`Reliable delivery failed for message ${deliveryId} after ${state.retryCount} retries to ${state.recipient.path}.`);
        const deadLetterTarget = this.config.deadLetterActorPath
          ? this.system.actorSelection(this.config.deadLetterActorPath).resolve()
          : this.system.deadLetters;

        if (deadLetterTarget) {
          deadLetterTarget.tell(state.message);
        }

        this.outbox.delete(deliveryId);
        continue;
      }

      this.sendOnce(state);
      state.retryCount++;
    }
  }

  private sendOnce(state: OutboundMessageState): void {
    const targetRef = this.system.actorSelection(state.recipient).resolve<ReliableEnvelope<any>>();

    if (targetRef) {
      const reliableMessage: ReliableEnvelope<any> = {
        __isReliableDelivery: true,
        deliveryId: state.deliveryId,
        senderAddress: state.sender?.address || null,
        originalMessage: state.message,
      };
      targetRef.tell(reliableMessage, state.sender);
    } else {
      console.warn(`Reliable delivery target ${state.recipient.path} not resolvable for deliveryId ${state.deliveryId}. Will retry.`);
    }
  }
}

export class SetReliableDeliveryRef implements SystemMessage {
  readonly __isSystemMessage = true;
  constructor(public readonly reliableDelivery: ReliableDelivery) {}
}

export class StopConfirmationActor implements SystemMessage {
  readonly __isSystemMessage = true;
}

export class ReliableDeliveryConfirmationActor extends Actor<DeliveryConfirmation | SetReliableDeliveryRef | StopConfirmationActor> {
  private reliableDelivery: ReliableDelivery | null = null;

  constructor(context: ActorContext) {
    super(context);
  }

  @Receive(SetReliableDeliveryRef)
  private onSetReliableDeliveryRef(message: SetReliableDeliveryRef): void {
    this.reliableDelivery = message.reliableDelivery;
  }

  @Receive(DeliveryConfirmation)
  private async onDeliveryConfirmation(message: DeliveryConfirmation): Promise<void> {
    if (this.reliableDelivery) {
      await this.reliableDelivery.confirmMessage(message.deliveryId, message.recipientAddress);
    } else {
      console.warn(`Received DeliveryConfirmation ${message.deliveryId} before ReliableDelivery service was set.`);
    }
  }

  @Receive(StopConfirmationActor)
  private onStopConfirmationActor(_message: StopConfirmationActor): void {
    this.context.stop(this.context.self);
  }
}
```
```tool_code
log_change
Added 'export' keyword to the class definitions of 'OutboundMessageSentEvent', 'MessageConfirmedEvent', 'ReliableDeliveryEvent' type alias, 'SetReliableDeliveryRef', 'StopConfirmationActor', and 'ReliableDeliveryConfirmationActor' in 'src/persistence/reliable-delivery.ts'.
