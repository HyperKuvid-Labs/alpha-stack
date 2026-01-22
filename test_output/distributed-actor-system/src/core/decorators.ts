import 'reflect-metadata';

export type ClassConstructor<T> = new (...args: any[]) => T;

export const MESSAGE_HANDLERS_METADATA_KEY = Symbol('__messageHandlers__');

export function Receive<T>(MessageType: ClassConstructor<T>): MethodDecorator {
  return function (target: Object, propertyKey: string | symbol, descriptor: PropertyDescriptor) {
    const handlers = Reflect.getMetadata(MESSAGE_HANDLERS_METADATA_KEY, target.constructor) || [];
    handlers.push({ messageType: MessageType, methodName: propertyKey });
    Reflect.defineMetadata(MESSAGE_HANDLERS_METADATA_KEY, handlers, target.constructor);
  };
}
