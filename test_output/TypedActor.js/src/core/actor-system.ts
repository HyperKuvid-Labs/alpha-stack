import { Actor, ActorProps, ActorConstructor } from './actor';
import { ActorRef } from './actor-ref';
import { ActorContext } from './actor-context';
import { Mailbox } from './mailbox';
import { Logger } from '../utils/logger';
import { Supervisor, SupervisionStrategy } from '../supervision/strategy';
import { PoisonPill, Failure } from '../types/messages';

interface ActorCell {
  actor: Actor<any>;
  ref: ActorRef<any>;
  context: ActorContext<any>;
  mailbox: Mailbox<any>;
  children: Map<string, ActorRef<any>>; // Map of child names to ActorRefs
  parentRef?: ActorRef<any>;
  path: string;
  props: ActorProps;
  status: 'running' | 'stopping' | 'stopped' | 'restarting';
  mailboxProcessingPromise?: Promise<void>;
  stopRequested: boolean;
}

export class ActorSystem {
  private static _instance: ActorSystem | undefined;
  private readonly _name: string;
  private readonly _logger: Logger;
  private readonly _actorRegistry: Map<string, ActorCell>; // Maps full path to ActorCell
  private readonly _userGuardianRef: ActorRef<any>; // Reference to the user guardian actor
  private readonly _systemGuardianRef: ActorRef<any>; // Internal system guardian
  private _isTerminating: boolean = false;
  private _isTerminated: boolean = false;

  private constructor(name: string, config: any = {}) {
    this._name = name;
    this._logger = new Logger(name);
    this._actorRegistry = new Map();

    this._systemGuardianRef = this.createSystemGuardian();
    this._userGuardianRef = this.createRootGuardian(this._systemGuardianRef);

    this._logger.info(`Actor System '${name}' created.`);
  }

  public static create(name: string = 'default', config: any = {}): ActorSystem {
    if (ActorSystem._instance && ActorSystem._instance._name !== name) {
      throw new Error(`ActorSystem "${ActorSystem._instance._name}" already running. Only one system can be created per application.`);
    }
    if (!ActorSystem._instance) {
      ActorSystem._instance = new ActorSystem(name, config);
    }
    return ActorSystem._instance;
  }

  private createSystemGuardian(): ActorRef<any> {
    class SystemGuardianActor extends Actor<any> {
      constructor(context: ActorContext<any>) {
        super(context);
        // The path for the system guardian is hardcoded as '/', it's the root.
      }
      preStart(): void {
        this.context.system.logger.info('System guardian started.');
      }
      postStop(): void {
        this.context.system.logger.info('System guardian stopped.');
      }
      async receive(message: any): Promise<void> {
        if (message instanceof Failure) {
          this.context.system.logger.error(`System Guardian received escalated failure from '${message.senderPath || 'unknown'}': ${message.reason}`);
        } else if (message instanceof PoisonPill) {
          // Handled by the mailbox loop, no explicit action here.
        } else {
          this.context.system.logger.warn(`System Guardian received unhandled message: ${message.constructor.name || typeof message}`);
        }
      }
    }

    const guardianProps: ActorProps = {
      actorClass: SystemGuardianActor,
      supervisorStrategy: new Supervisor((error: Error) => SupervisionStrategy.Stop),
    };

    const systemGuardianMailbox = new Mailbox<any>();
    const systemGuardianRef = new ActorRef<any>('/', this);
    const systemGuardianContext = new ActorContext<any>(systemGuardianRef, undefined, this);
    const systemGuardianInstance = new SystemGuardianActor(systemGuardianContext);

    const systemGuardianCell: ActorCell = {
      actor: systemGuardianInstance,
      ref: systemGuardianRef,
      context: systemGuardianContext,
      mailbox: systemGuardianMailbox,
      children: new Map(),
      path: '/',
      props: guardianProps,
      status: 'running',
      stopRequested: false
    };
    this._actorRegistry.set('/', systemGuardianCell);
    systemGuardianInstance.preStart();
    systemGuardianCell.mailboxProcessingPromise = this.runMailbox(systemGuardianCell);

    return systemGuardianRef;
  }

  private createRootGuardian(systemGuardianRef: ActorRef<any>): ActorRef<any> {
    class UserGuardianActor extends Actor<any> {
      constructor(context: ActorContext<any>) {
        super(context);
      }
      preStart(): void {
        this.context.system.logger.info('User guardian started.');
      }
      postStop(): void {
        this.context.system.logger.info('User guardian stopped.');
      }
      async receive(message: any): Promise<void> {
        if (message instanceof Failure) {
          this.context.system.logger.error(`User Guardian received escalated failure from '${message.senderPath || 'unknown'}': ${message.reason}`);
          const childPath = message.senderPath;
          const childName = childPath?.split('/').pop();
          if (childName) {
            const childRef = this.context.children.get(childName);
            if (childRef) {
              this.context.stop(childRef);
            }
          }
        } else if (message instanceof PoisonPill) {
          // Handled by the mailbox loop
        } else {
          this.context.system.logger.warn(`User Guardian received unhandled message: ${message.constructor.name || typeof message}`);
        }
      }
    }

    const guardianProps: ActorProps = {
      actorClass: UserGuardianActor,
      supervisorStrategy: new Supervisor((error: Error) => SupervisionStrategy.Escalate),
    };

    const userGuardianRef = this.internalSpawn(systemGuardianRef, guardianProps, 'user');

    const systemGuardianCell = this._actorRegistry.get(systemGuardianRef.path);
    if (systemGuardianCell) {
      systemGuardianCell.children.set('user', userGuardianRef);
    }
    return userGuardianRef;
  }

  public get name(): string {
    return this._name;
  }

  public get logger(): Logger {
    return this._logger;
  }

  public getRef(path: string): ActorRef<any> | undefined {
    const cell = this._actorRegistry.get(path);
    return cell ? cell.ref : undefined;
  }

  public spawn<T>(props: ActorProps<T>, name?: string): ActorRef<T> {
    if (this._isTerminating || this._isTerminated) {
      throw new Error(`ActorSystem '${this._name}' is terminating or terminated. Cannot spawn new actors.`);
    }
    return this.internalSpawn(this._userGuardianRef, props, name) as ActorRef<T>;
  }

  public internalSpawn<T>(parentRef: ActorRef<any>, props: ActorProps<T>, name?: string): ActorRef<T> {
    const parentCell = this._actorRegistry.get(parentRef.path);
    if (!parentCell || parentCell.status === 'stopping' || parentCell.status === 'stopped' || parentCell.stopRequested) {
      throw new Error(`Parent actor at path '${parentRef.path}' not found or is stopping/stopped. Cannot spawn child actor.`);
    }

    let actorName = name || `actor-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    const parentPathPrefix = parentRef.path === '/' ? '' : parentRef.path;
    let actorPath = `${parentPathPrefix}/${actorName}`;

    let counter = 0;
    while (this._actorRegistry.has(actorPath)) {
      counter++;
      actorName = `${name || `actor`}-${Date.now()}-${Math.random().toString(36).substring(2, 9)}-${counter}`;
      actorPath = `${parentPathPrefix}/${actorName}`;
    }

    const newActorRef = new ActorRef<T>(actorPath, this);
    const mailbox = new Mailbox<T>();
    const context = new ActorContext<T>(newActorRef, parentRef, this);

    const actorInstance = new props.actorClass(context);

    const actorCell: ActorCell = {
      actor: actorInstance,
      ref: newActorRef,
      context: context,
      mailbox: mailbox,
      children: new Map(),
      parentRef: parentRef,
      path: actorPath,
      props: props,
      status: 'running',
      stopRequested: false
    };

    this._actorRegistry.set(actorPath, actorCell);
    parentCell.children.set(actorName, newActorRef);

    actorInstance.preStart();
    actorCell.mailboxProcessingPromise = this.runMailbox(actorCell);

    this._logger.info(`Actor '${actorPath}' spawned.`);
    return newActorRef;
  }

  public internalStop(actorRef: ActorRef<any>): void {
    const actorCell = this._actorRegistry.get(actorRef.path);
    if (!actorCell || actorCell.status === 'stopping' || actorCell.status === 'stopped' || actorCell.stopRequested) {
      return;
    }

    this._logger.info(`Stopping actor '${actorRef.path}'...`);
    actorCell.status = 'stopping';
    actorCell.stopRequested = true;

    for (const childRef of actorCell.children.values()) {
      this.internalStop(childRef);
    }

    actorCell.mailbox.enqueue(new PoisonPill() as any);
  }

  private async processPoisonPill(actorCell: ActorCell): Promise<void> {
    this._logger.info(`Actor '${actorCell.path}' received PoisonPill. Performing postStop.`);
    actorCell.actor.postStop();

    if (actorCell.parentRef) {
      const parentCell = this._actorRegistry.get(actorCell.parentRef.path);
      if (parentCell) {
        const actorName = actorCell.path.split('/').pop();
        if (actorName) {
          parentCell.children.delete(actorName);
        }
      }
    }

    this._actorRegistry.delete(actorCell.path);
    actorCell.status = 'stopped';
    this._logger.info(`Actor '${actorCell.path}' stopped and removed from system.`);
  }

  private async restartActor(actorCell: ActorCell): Promise<void> {
    this._logger.warn(`Restarting actor '${actorCell.path}'.`);
    actorCell.status = 'restarting';
    actorCell.actor.preRestart();

    const newContext = new ActorContext<any>(actorCell.ref, actorCell.parentRef, this);
    const newActorInstance = new actorCell.props.actorClass(newContext);

    actorCell.actor = newActorInstance;
    actorCell.context = newContext;
    actorCell.status = 'running';
    actorCell.stopRequested = false;

    newActorInstance.postRestart();
    this._logger.info(`Actor '${actorCell.path}' restarted.`);
  }

  private async runMailbox(actorCell: ActorCell): Promise<void> {
    try {
      for await (const message of actorCell.mailbox.messages()) {
        if (actorCell.stopRequested) {
          if (message instanceof PoisonPill) {
            await this.processPoisonPill(actorCell);
          }
          break;
        }

        if (message instanceof PoisonPill) {
          await this.processPoisonPill(actorCell);
          break;
        }

        try {
          await actorCell.actor.receive(message);
        } catch (error) {
          this._logger.error(`Error in actor '${actorCell.path}' while processing message: ${error}`);

          const strategy = actorCell.props.supervisorStrategy?.decider(error as Error) || SupervisionStrategy.Escalate;

          switch (strategy) {
            case SupervisionStrategy.Stop:
              this._logger.warn(`Supervision: Stopping actor '${actorCell.path}' due to error.`);
              this.internalStop(actorCell.ref);
              break;
            case SupervisionStrategy.Restart:
              this._logger.warn(`Supervision: Restarting actor '${actorCell.path}' due to error.`);
              await this.restartActor(actorCell);
              break;
            case SupervisionStrategy.Resume:
              this._logger.warn(`Supervision: Resuming actor '${actorCell.path}' after error.`);
              break;
            case SupervisionStrategy.Escalate:
              this._logger.warn(`Supervision: Escalating failure from '${actorCell.path}'.`);
              if (actorCell.parentRef) {
                actorCell.parentRef.tell(new Failure(error as Error, actorCell.path));
              } else {
                this._logger.error(`Unsupervised failure at root actor '${actorCell.path}': ${error}`);
                this.internalStop(actorCell.ref);
              }
              break;
          }
        }
      }
    } catch (err) {
      this._logger.error(`Mailbox loop for '${actorCell.path}' failed catastrophically: ${err}`);
      this.internalStop(actorCell.ref);
    } finally {
      if (actorCell.status !== 'stopped' && actorCell.status !== 'restarting') {
        this._logger.warn(`Mailbox loop for '${actorCell.path}' exited unexpectedly. Forcing stop.`);
        this.internalStop(actorCell.ref);
      }
    }
  }

  public async terminate(): Promise<void> {
    if (this._isTerminating || this._isTerminated) {
      this._logger.warn(`ActorSystem '${this._name}' is already terminating or terminated.`);
      return;
    }
    this._isTerminating = true;
    this._logger.info(`Actor System '${this._name}' initiating termination...`);

    if (this._userGuardianRef) {
      this.internalStop(this._userGuardianRef);
    }

    let terminationAttempts = 0;
    const maxTerminationAttempts = 200; // Max wait time 200 * 50ms = 10 seconds

    while (this._actorRegistry.size > 1 && terminationAttempts < maxTerminationAttempts) {
      await new Promise(resolve => setTimeout(resolve, 50));
      terminationAttempts++;
    }
    if (this._actorRegistry.size > 1) {
        this._logger.warn(`Timed out waiting for ${this._actorRegistry.size - 1} user actors to terminate.`);
    }

    if (this._systemGuardianRef) {
      this.internalStop(this._systemGuardianRef);
    }

    terminationAttempts = 0;
    while (this._actorRegistry.size > 0 && terminationAttempts < maxTerminationAttempts) {
      await new Promise(resolve => setTimeout(resolve, 50));
      terminationAttempts++;
    }
    if (this._actorRegistry.size > 0) {
        this._logger.error(`Timed out waiting for ${this._actorRegistry.size} system actors to terminate. Registry not empty.`);
    }

    await Promise.allSettled(
      Array.from(this._actorRegistry.values())
        .filter(cell => cell.mailboxProcessingPromise)
        .map(cell => cell.mailboxProcessingPromise)
    );

    this._isTerminated = true;
    this._isTerminating = false;
    ActorSystem._instance = undefined;
    this._logger.info(`Actor System '${this._name}' terminated.`);
  }
}
