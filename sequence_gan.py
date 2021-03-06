import numpy as np
import tensorflow as tf
import random
from dataloader import Gen_Data_loader, Dis_dataloader
from generator import Generator
from discriminator import Discriminator
from rollout import ROLLOUT
import argparse

length_dict = {'chandler': 175, 'ross': 198, 'phoebe': 317, 'monica': 279, 'rachel': 247}
dictionary_dict = {'chandler': 7368, 'ross': 7855, 'phoebe': 6818, 'monica': 6482, 'rachel': 7159}

#########################################################################################
#  Generator  Hyper-parameters
######################################################################################
EMB_DIM = 32 # embedding dimension
HIDDEN_DIM = 32 # hidden state dimension of lstm cell
SEQ_LENGTH = 0 # sequence length {'Chandler': 175, 'Ross': 198, 'Phoebe': 317, 'Monica': 279, 'Rachel': 247}
START_TOKEN = 0
PRE_EPOCH_NUM = 120 # supervise (maximum likelihood estimation) epochs
SEED = 88
BATCH_SIZE = 64

#########################################################################################
#  Discriminator  Hyper-parameters
#########################################################################################
dis_embedding_dim = 64
dis_filter_sizes = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20]
dis_num_filters = [100, 200, 200, 200, 200, 100, 100, 100, 100, 100, 160, 160]
dis_dropout_keep_prob = 0.75
dis_l2_reg_lambda = 0.2
dis_batch_size = 64

#########################################################################################
#  Basic Training Parameters
#########################################################################################
TOTAL_BATCH = 25 #200
# positive_file = 'save/real_data.txt'
positive_file = 'save/chandler_lines.txt'
negative_file = 'save/generator_sample.txt'
eval_file = 'save/eval_file.txt'
generated_num = 10000
log_file = "save/log_file.txt"

def create_log():
    with open(log_file, "w") as f:
        f.write("")

def write_to_log(string):
    with open(log_file, "a") as f:
        f.write(string + "\n")

def generate_samples(sess, trainable_model, batch_size, generated_num, output_file):
    # Generate Samples
    generated_samples = []
    for _ in range(int(generated_num / batch_size)):
        generated_samples.extend(trainable_model.generate(sess))

    with open(output_file, 'w') as fout:
        for poem in generated_samples:
            buffer = ' '.join([str(x) for x in poem]) + '\n'
            fout.write(buffer)


def target_loss(sess, target_lstm, data_loader):
    # target_loss means the oracle negative log-likelihood tested with the oracle model "target_lstm"
    # For more details, please see the Section 4 in https://arxiv.org/abs/1609.05473
    nll = []
    data_loader.reset_pointer()

    for it in range(data_loader.num_batch):
        batch = data_loader.next_batch()
        g_loss = sess.run(target_lstm.pretrain_loss, {target_lstm.x: batch})
        nll.append(g_loss)

    return np.mean(nll)


def pre_train_epoch(sess, trainable_model, data_loader):
    # Pre-train the generator using MLE for one epoch
    supervised_g_losses = []
    data_loader.reset_pointer()

    for it in range(data_loader.num_batch):
        batch = data_loader.next_batch()
        _, g_loss = trainable_model.pretrain_step(sess, batch)
        supervised_g_losses.append(g_loss)

    return np.mean(supervised_g_losses)


def main(character):
    print("Processing character : \"{}\"".format(character))
    write_to_log("Processing character : \"{}\"".format(character))

    vocab_size = dictionary_dict[character]
    SEQ_LENGTH = length_dict[character]
    positive_file = "save/{}_lines.txt".format(character)
    output_file = "save/new_{}_lines.txt".format(character)

    random.seed(SEED)
    np.random.seed(SEED)
    assert START_TOKEN == 0

    # need for v1 -> v2 port
    tf.compat.v1.disable_eager_execution()

    create_log()

    gen_data_loader = Gen_Data_loader(BATCH_SIZE)
    likelihood_data_loader = Gen_Data_loader(BATCH_SIZE) # For testing

    dis_data_loader = Dis_dataloader(BATCH_SIZE)

    generator = Generator(vocab_size, BATCH_SIZE, EMB_DIM, HIDDEN_DIM, SEQ_LENGTH, START_TOKEN)
    # target_params = cPickle.load(open('save/target_params.pkl'))
    # target_lstm = TARGET_LSTM(vocab_size, BATCH_SIZE, EMB_DIM, HIDDEN_DIM, SEQ_LENGTH, START_TOKEN, target_params) # The oracle model

    discriminator = Discriminator(sequence_length=SEQ_LENGTH, num_classes=2, vocab_size=vocab_size, embedding_size=dis_embedding_dim, 
                                filter_sizes=dis_filter_sizes, num_filters=dis_num_filters, l2_reg_lambda=dis_l2_reg_lambda)

    config = tf.compat.v1.ConfigProto()
    config.gpu_options.allow_growth = True
    sess = tf.compat.v1.Session(config=config)
    sess.run(tf.compat.v1.global_variables_initializer())

    # First, use the oracle model to provide the positive examples, which are sampled from the oracle data distribution
    # generate_samples(sess, target_lstm, BATCH_SIZE, generated_num, positive_file)

    gen_data_loader.create_batches(positive_file)

    log = open('save/experiment-log.txt', 'w')
    #  pre-train generator
    print('Start pre-training...')
    write_to_log('Start pre-training...')

    for epoch in range(PRE_EPOCH_NUM):
        loss = pre_train_epoch(sess, generator, gen_data_loader)
        if epoch % 5 == 0:
            generate_samples(sess, generator, BATCH_SIZE, generated_num, eval_file)
            likelihood_data_loader.create_batches(eval_file)
            # test_loss = target_loss(sess, target_lstm, likelihood_data_loader)
            # print 'pre-train epoch ', epoch, 'test_loss ', test_loss
            # buffer = 'epoch:\t'+ str(epoch) + '\tnll:\t' + str(test_loss) + '\n'
            # log.write(buffer)
        print("Iteration {} complete".format(epoch))
        write_to_log("Iteration {} complete".format(epoch))

    # print('Start pre-training discriminator...')
    # write_to_log('Start pre-training discriminator...')

    # # Train 3 epoch on the generated data and do this for 50 times
    # for _ in range(50):
    # # for _ in range(1):
    #     generate_samples(sess, generator, BATCH_SIZE, generated_num, negative_file)
    #     dis_data_loader.load_train_data(positive_file, negative_file)
    #     for _ in range(3):
    #     # for _ in range(1):
    #         dis_data_loader.reset_pointer()
    #         for it in range(dis_data_loader.num_batch):
    #             x_batch, y_batch = dis_data_loader.next_batch()
    #             feed = {
    #                 discriminator.input_x: x_batch,
    #                 discriminator.input_y: y_batch,
    #                 discriminator.dropout_keep_prob: dis_dropout_keep_prob
    #             }
    #             _ = sess.run(discriminator.train_op, feed)

    #     print("Iteration {} complete".format(_))
    #     write_to_log("Iteration {} complete".format(_))

    # rollout = ROLLOUT(generator, 0.8)

    # print('#########################################################################')
    # write_to_log('#########################################################################')

    # print('Start Adversarial Training...')
    # write_to_log('Start Adversarial Training...')

    # for total_batch in range(TOTAL_BATCH):
    # # for total_batch in range(1):
    #     # Train the generator for one step
    #     for it in range(1):
    #         samples = generator.generate(sess)
    #         rewards = rollout.get_reward(sess, samples, 16, discriminator)
    #         feed = {generator.x: samples, generator.rewards: rewards}
    #         _ = sess.run(generator.g_updates, feed_dict=feed)

    #     # Test
    #     if total_batch % 5 == 0 or total_batch == TOTAL_BATCH - 1:
    #         generate_samples(sess, generator, BATCH_SIZE, generated_num, eval_file)
    #         likelihood_data_loader.create_batches(eval_file)
    #         # test_loss = target_loss(sess, target_lstm, likelihood_data_loader)
    #         # buffer = 'epoch:\t' + str(total_batch) + '\tnll:\t' + str(test_loss) + '\n'
    #         # print 'total_batch: ', total_batch, 'test_loss: ', test_loss
    #         # log.write(buffer)
        
    #     print("Generator iteration {} complete".format(total_batch))
    #     write_to_log("Generator iteration {} complete".format(total_batch))

    #     # Update roll-out parameters
    #     rollout.update_params()

    #     # Train the discriminator
    #     for _ in range(5):
    #     # for _ in range(1):
    #         generate_samples(sess, generator, BATCH_SIZE, generated_num, negative_file)
    #         dis_data_loader.load_train_data(positive_file, negative_file)

    #         for _ in range(3):
    #         # for _ in range(1):
    #             dis_data_loader.reset_pointer()
    #             for it in range(dis_data_loader.num_batch):
    #                 x_batch, y_batch = dis_data_loader.next_batch()
    #                 feed = {
    #                     discriminator.input_x: x_batch,
    #                     discriminator.input_y: y_batch,
    #                     discriminator.dropout_keep_prob: dis_dropout_keep_prob
    #                 }
    #                 _ = sess.run(discriminator.train_op, feed)

    #     print("Discriminator iteration {} complete".format(total_batch))
    #     write_to_log("Discriminator iteration {} complete".format(total_batch))


    print("Writing final output...")
    write_to_log("Writing final output...")

    # Final output is a list of new lines the character "would" say
    generate_samples(sess, generator, BATCH_SIZE, 100000, output_file)

    log.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Get name of character whose lines to generate')
    parser.add_argument('--character')
    args = parser.parse_args()

    # print(args.character.lower())

    main(args.character.lower())
