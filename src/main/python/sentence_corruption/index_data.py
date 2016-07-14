from nltk.tokenize import word_tokenize
import numpy
import math
import itertools

class DataIndexer(object):
    def __init__(self):
        self.word_index = {"PADDING":0}
        self.reverse_word_index = {0: "PADDING"}

    def index_sentence(self, sentence, tokenize):
        words = word_tokenize(sentence) if tokenize else sentence.split()
        # Adding start and end tags after tokenization to avoid tokenizing those symbols
        words = ['<s>'] + words + ['</s>']
        indices = []
        for word in words:
            if word not in self.word_index:
                index = len(self.word_index)
                self.word_index[word] = index
                self.reverse_word_index[index] = word
            indices.append(self.word_index[word])
        return indices

    def index_data(self, sentences, max_length=None, tokenize=True):
        all_indices = []
        for sentence in sentences:
            sentence_indices = self.index_sentence(sentence, tokenize=tokenize)
            all_indices.append(sentence_indices)
        # Note: sentence_length includes start and end symbols as well.
        sentence_lengths = [len(indices) for indices in all_indices]
        if not max_length:
            max_length = max(sentence_lengths)
        all_indices_array = numpy.zeros((len(all_indices), max_length))
        for i, indices in enumerate(all_indices):
            all_indices_array[i][-len(indices):] = indices
        return sentence_lengths, all_indices_array

    def _make_one_hot(self, target_indices, vector_size):
        # Convert integer indices to one-hot vectors
        one_hot_vectors = numpy.zeros(target_indices.shape + (vector_size,))
        # Each index in the loop below is of a vector in the one-hot array
        # i.e. if the shape of target_indices is (5, 6), the indices will come from
        # the cartesian product of the sets {0,1,2,3,4} and {0,1,2,3,4,5}
        # Note: this works even if target_indices is a higher order tensor.
        for index in itertools.product(*[numpy.arange(s) for s in target_indices.shape]):
            # If element at (p, q) in target_indices is r, make (p, q, r) in the 
            # one hot array 1.
            full_one_hot_index = index + (target_indices[index],)
            one_hot_vectors[full_one_hot_index] = 1
        return one_hot_vectors

    def factor_target_indices(self, target_indices, base=2):
        # Factor target indices into a hierarchy of depth log(base)
        # i.e. one integer index will be converted into log_{base}(vocab_size) 
        # arrays, each of size = base.
        # Essentially coverting given integers to the given base, but operating
        # on arrays instead.
        vocab_size = target_indices.max() + 1
        num_digits_per_word = int(math.ceil(math.log(vocab_size) / math.log(base)))
        all_factored_arrays = []
        # We'll keep dividing target_indices by base and storing the remainders as
        # factored arrays. Start by making a temp copy of the original indices.
        temp_target_indices = target_indices
        for i in range(num_digits_per_word):
            factored_arrays = temp_target_indices % base
            if i == num_digits_per_word - 1:
                if factored_arrays.sum() == 0:
                    # Most significant "digit" is 0. Ignore it.
                    break
            all_factored_arrays.append(factored_arrays)
            temp_target_indices = numpy.copy(temp_target_indices / base)
        # Note: Most significant digit first.
        # Now get one hot vectors of the factored arrays
        all_one_hot_factored_arrays = [self._make_one_hot(array, base) for 
                array in all_factored_arrays]
        return all_one_hot_factored_arrays

    def unfactor_probabilities(self, probabilities):
        # Given probabilities at all factored digits, compute the probabilities
        # of all indices. For example, if the factored indices had five digits of 
        # base 2, and we get probabilities of both bits at all five digits, we can 
        # use those to calculate the probabilities of all 2 ** 5 = 32 words.
        num_digits_per_word = len(probabilities)
        base = len(probabilities[0])
        word_log_probabilities = []
        for factored_index in itertools.product(*[[b for b in range(base)]]*num_digits_per_word):
            
            index = sum([(base ** i) * factored_index[i] for i in range(num_digits_per_word)]) 
            word = self.get_word_from_index(index)
            if word:
                log_probs = [math.log(probabilities[i][factored_index[i]]) for 
                        i in range(num_digits_per_word)]
                log_probability = sum(log_probs)
                word_log_probabilities.append((log_probability, word))
        return sorted(word_log_probabilities, reverse=True)

    def get_word_from_index(self, index):
        return self.reverse_word_index[index] if index in self.reverse_word_index else None

    def get_vocab_size(self):
        return len(self.word_index)
