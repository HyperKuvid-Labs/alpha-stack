import { describe, it, expect, mock, beforeEach } from 'bun:test';

const mockDispatch = mock(() => {});
const mockAsk = mock(async (address: any, message: any, timeout?: number) => {
	if (message.type === 'fail') {
		throw new Error('System ask failed');
	}
	return `response_for_${message.type}`;
});

mock.module('./actor-system', () => {
	return {
		ActorSystem: class MockActorSystem {
			dispatch = mockDispatch;
			ask = mockAsk;
			constructor(name: string) {}
		},
	};
});

import { ActorRef } from './actor-ref';
import { ActorSystem } from './actor-system';
import type { ActorAddress } from '../types/actor.types';

describe('ActorRef', () => {
	let mockSystemInstance: ActorSystem;
	let testAddress: ActorAddress;
	let actorRef: ActorRef<{ type: string }>;
	let senderRef: ActorRef<{ type: string }>;

	beforeEach(() => {
		mockDispatch.mockClear();
		mockAsk.mockClear();

		mockSystemInstance = new ActorSystem('test-system');

		testAddress = {
			protocol: 'local',
			system: 'test-system',
			host: 'localhost',
			port: 1234,
			path: ['user', 'test-actor'],
		};

		const senderAddress: ActorAddress = {
			protocol: 'local',
			system: 'test-system',
			host: 'localhost',
			port: 1234,
			path: ['user', 'sender-actor'],
		};

		actorRef = new ActorRef(testAddress, mockSystemInstance);
		senderRef = new ActorRef(senderAddress, mockSystemInstance);
	});

	it('should be created with a valid address and system reference', () => {
		expect(actorRef).toBeInstanceOf(ActorRef);
		expect(actorRef.address).toBe(testAddress);
		// @ts-ignore
		expect(actorRef._system).toBe(mockSystemInstance);
	});

	it('should provide the correct actor path string', () => {
		expect(actorRef.path).toBe('/user/test-actor');
	});

	it('should handle an empty path gracefully', () => {
		const rootAddress: ActorAddress = { ...testAddress, path: [] };
		const rootRef = new ActorRef(rootAddress, mockSystemInstance);
		expect(rootRef.path).toBe('/');
	});

	describe('tell()', () => {
		it('should dispatch a message to the system without a sender', () => {
			const message = { type: 'fire-and-forget' };
			actorRef.tell(message);

			expect(mockDispatch).toHaveBeenCalledTimes(1);
			expect(mockDispatch).toHaveBeenCalledWith({
				recipient: testAddress,
				message: message,
				sender: undefined,
			});
		});

		it('should dispatch a message to the system with a sender', () => {
			const message = { type: 'message-with-sender' };
			actorRef.tell(message, senderRef);

			expect(mockDispatch).toHaveBeenCalledTimes(1);
			expect(mockDispatch).toHaveBeenCalledWith({
				recipient: testAddress,
				message: message,
				sender: senderRef,
			});
		});
	});

	describe('ask()', () => {
		it('should send a message via the system and resolve with a response', async () => {
			const message = { type: 'question' };
			const response = await actorRef.ask(message, 1000);

			expect(mockAsk).toHaveBeenCalledTimes(1);
			expect(mockAsk).toHaveBeenCalledWith(testAddress, message, 1000);
			expect(response).toBe('response_for_question');
		});

		it('should use the default timeout if none is provided', async () => {
			const message = { type: 'another-question' };
			await actorRef.ask(message);

			expect(mockAsk).toHaveBeenCalledTimes(1);
			expect(mockAsk).toHaveBeenCalledWith(testAddress, message, 5000);
		});

		it('should reject if the system ask method fails', async () => {
			const message = { type: 'fail' };

			await expect(actorRef.ask(message)).rejects.toThrow('System ask failed');
			expect(mockAsk).toHaveBeenCalledTimes(1);
			expect(mockAsk).toHaveBeenCalledWith(testAddress, message, 5000);
		});

		it('should correctly infer return type from generic', async () => {
			const message = { type: 'get-string' };
			const response: string = await actorRef.ask<string>(message);

			expect(mockAsk).toHaveBeenCalledTimes(1);
			expect(response).toBe('response_for_get-string');
			expect(typeof response).toBe('string');
		});

		it('should handle a zero timeout value', async () => {
			const message = { type: 'quick-question' };
			await actorRef.ask(message, 0);

			expect(mockAsk).toHaveBeenCalledTimes(1);
			expect(mockAsk).toHaveBeenCalledWith(testAddress, message, 0);
		});
	});
});
