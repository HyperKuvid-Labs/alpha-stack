export abstract class Message {}

export type ClassConstructor<T> = new (...args: any[]) => T;
