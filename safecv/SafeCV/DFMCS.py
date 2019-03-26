# -*- coding: utf-8 -*-
import cv2
import numpy as np
from pomegranate import NormalDistribution
import math
import copy
import sys


def white_manip(value, epsilon, dim=3):
    return [255, 255, 255]


def UCB1(keypoint_distribution, plays_per_node, totalplays):
    retval = []
    for i in range(len(keypoint_distribution)):
        value = keypoint_distribution[i]
        value += math.sqrt(math.log(plays_per_node[i])/totalplays)
        retval.append(value)
    retval = np.asarray(retval)
    return retval/sum(retval)


class DFMCS_Parameters:
    def __init__(self, image, true_class, model, predshape=(1, 224, 224, 3)):
        self.model = model
        self.ORIGINAL_IMAGE = copy.deepcopy(image)
        self.TRUE_CLASS = true_class
        self.SIGMA_CONSTANT = 15
        self.VISIT_CONSTANT = 5
        self.manip_method = white_manip
        self.X_SHAPE = 224
        self.Y_SHAPE = 223
        self.predshape = predshape
        self.EPSILON = 50
        self.MANIPULATIONS = []
        self.TOTAL_PLAYS = 1
        self.PLAYS_ARRAY = np.ones(len(self.kp))
        self.MISCLASSIFIED = False
        self.verbose = False
        self.small_image = False
        self.inflation_constant = 15
        self.kp, self.des, self.r = [], [], []

        def preproc(im):
            im_pred = IMAGE.reshape(params.predshape)
            im_pred = im_pred.astype('float')
            return image

        self.preprocess = preproc

        def predi(im):
            im = self.preprocess(im)
            prob = self.model.predict(im_pred, batch_size=1, verbose=0)
            pred = np.argmax(np.asarray(prob))
            return pred, prob

        self.predict = predi
        pred, prob = self.predict(image)
        self.PROBABILITY = max(max(prob))
        self.SOFT_MAX_ARRAY = prob
        self.backtracking_constant = 10

    def __init__(self, MCTS_params, image):
        self.model = MCTS_params.model
        self.ORIGINAL_IMAGE = copy.deepcopy(image)
        self.TRUE_CLASS = MCTS_params.TRUE_CLASS
        self.manip_method = MCTS_params.MANIP
        self.VISIT_CONSTANT = MCTS_params.VISIT_CONSTANT
        self.SIGMA_CONSTANT = MCTS_params.SIGMA_CONSTANT
        self.X_SHAPE = MCTS_params.X_SHAPE
        self.Y_SHAPE = MCTS_params.Y_SHAPE
        self.predshape = MCTS_params.predshape
        self.kp = MCTS_params.kp
        self.des = MCTS_params.des
        self.r = MCTS_params.r
        self.EPSILON = 50
        self.MANIPULATIONS = []
        self.TOTAL_PLAYS = 1
        self.PLAYS_ARRAY = np.ones(len(self.kp))
        self.MISCLASSIFIED = False
        self.verbose = MCTS_params.verbose
        self.preprocess = MCTS_params.preprocess
        self.predict = MCTS_params.predict
        self.small_image = MCTS_params.small_image
        self.inflation_constant = 15
        pred, prob = self.predict(image)
        self.PROBABILITY = max(max(prob))
        self.SOFT_MAX_ARRAY = prob
        self.backtracking_constant = MCTS_params.backtracking_constant


def SIFT_Filtered(image, parameters, threshold=0.00):
    # We need to expand the image to get good keypoints
    if(parameters.small_image):
        xs = parameters.X_SHAPE * parameters.inflation_constant
        ys = parameters.Y_SHAPE * parameters.inflation_constant
        image = cv2.resize(image, (xs, ys))

    sift = cv2.xfeatures2d.SIFT_create()
    kp, des = sift.detectAndCompute(image, None)
    # FILTER RESPONSES:
    responses = []
    for x in kp:
        responses.append(x.response)
    responses.sort()
    ret = []
    index_tracker = 0
    for x in kp:
        if(x.response >= threshold):
            ret.append((x, des[index_tracker], x.response))
        index_tracker = index_tracker + 1
    retval = sorted(ret, key=lambda tup: tup[2])
    return zip(*retval)

"""
Input: image, true_class, manip_method, kp_selection (optional)
Output: adv_image, softmax_array, L0 Severity, kp_selection
"""


def DFMCS(params, cutoff=-1):
    image = copy.deepcopy(params.ORIGINAL_IMAGE)
    if(params.kp == []):
        temp_params = SIFT_Filtered(params.ORIGINAL_IMAGE, params)
        params.kp = temp_params[0]
        params.des = temp_params[1]
        params.r = temp_params[2]
        params.r = np.asarray(params.r)
        params.r = params.r/sum(params.r)
    if(cutoff != -1):
        enforce_cutoff = True
    else:
        enforce_cutoff = False

    def sample_from_kp(k):
        mu_x, mu_y, sigma = int(round(k.pt[0])), int(round(k.pt[1])),  k.size
        # Remember, it may be wise to expand simga
        #  greater varience = less honed attack
        sigma += params.SIGMA_CONSTANT
        d_x = NormalDistribution(mu_x, sigma)
        d_y = NormalDistribution(mu_y, sigma)
        x = d_x.sample()
        y = d_y.sample()
        if(params.small_image):
            x /= params.inflation_constant
            y /= params.inflation_constant
        x = int(x)
        y = int(y)
        if(x >= params.X_SHAPE):
            x = params.X_SHAPE-1
        elif(x < 0):
            x = 0
        if(y >= params.Y_SHAPE):
            y = params.Y_SHAPE-1
        elif(y < 0):
            y = 0
        return int(x), int(y)

    def backprop(keypoint_distribution, expored_index, reward):
        keypoint_distribution[expored_index] += (float(reward)/25)
        if(keypoint_distribution[expored_index] < 0):
            keypoint_distribution[expored_index] = 0
        # keypoint_distribution += (max(keypoint_distribution)/4)
        keypoint_distribution /= sum(keypoint_distribution)
        return keypoint_distribution

    def calculate_reward(orig, new, true_class, target_class=None):
        if(target_class is None):
            return orig[0][true_class] - new[0][true_class]
        else:
            return new[0][target_class] - orig[0][target_class]

    def calculate_cumulative_reward(orig, new, true_class, target_class):
        sum_reward = 0
        for i in target_class:
            sum_reward += orig[0][i] - new[0][i]
        return sum_reward/len(target_class)

    def run_mcts_exploitation_step(model, image, true_class, keypoints,
                                   keypoint_distribution, backpropogation,
                                   TOTAL_PLAYS, target_class=None):
        for i in range(len(keypoint_distribution)):
            if(keypoint_distribution[i] < 0):
                keypoint_distribution[i] = 0
        keypoint_distribution = np.asarray(keypoint_distribution)
        keypoint_distribution /= sum(keypoint_distribution)
        # Choose a keypoint from the keypoint distribution (exploitation)
        kp_len_array = range(len(keypoint_distribution))
        kis = np.random.choice(kp_len_array, p=keypoint_distribution)
        # (4b) - Expore that keypoint up to some bound
        expiter = 0
        while(expiter != params.VISIT_CONSTANT):
            x, y = sample_from_kp(keypoints[kis])
            try:
                if(((x, y) in params.MANIPULATIONS) or
                   list(image[y][x]) ==
                   list(params.manip_method(image[y][x], params.EPSILON))):
                    continue
            except:
                if(((x, y) in params.MANIPULATIONS) or
                   (image[y][x]) ==
                   (params.manip_method(image[y][x], params.EPSILON))):
                    continue

            image[y][x] = params.manip_method(image[y][x], params.EPSILON)
            params.MANIPULATIONS.append((x, y))

            expiter += 1

        pred, prob = params.predict(image)
        if((pred != int(true_class) and target_class is None) or
           (pred != target_class and target_class is not None)):
            if(params.verbose):
                print("\n")
                print("Adversarial Example Found")
                f = """Current Probability: %s
                       Current Class: %s
                       Manipulations: %s
                """ % (prob[0][pred], pred, len(params.MANIPULATIONS))
                sys.stdout.write("\r" + str(f))
                sys.stdout.flush()
            MISCLASSIFIED = True
            return keypoint_distribution, image, TOTAL_PLAYS, MISCLASSIFIED

        # !*!
        reward = calculate_reward(params.SOFT_MAX_ARRAY,
                                  prob, true_class, target_class)

        if(reward < 0):
            replace = params.MANIPULATIONS[-params.VISIT_CONSTANT:]
            for x, y in replace:
                image[y][x] = params.ORIGINAL_IMAGE[y][x]
        MISCLASSIFIED = False
        # (4c) - Backpropogation
        keypoint_distribution = backpropogation(keypoint_distribution,
                                                kis, reward)
        params.PLAYS_ARRAY[kis] += 1
        params.TOTAL_PLAYS += 1
        if(params.verbose):
            f = """Current Probability: %s
                   Current Class: %s
                   Manipulations: %s
                """ % (prob[0][pred], pred, len(params.MANIPULATIONS))
            sys.stdout.write("\r" + str(f))
            sys.stdout.flush()
        return keypoint_distribution, image, TOTAL_PLAYS, MISCLASSIFIED

    def run_mcts_exploration_step(model, image, true_class,
                                  keypoints, keypoint_distribution,
                                  backpropogation, PLAYS_ARRAY,
                                  TOTAL_PLAYS, target_class=None):
        # Choose a keypoint from the keypoint distribution (exploitation)
        kis = np.random.choice(range(len(keypoint_distribution)),
                               p=UCB1(keypoint_distribution,
                               PLAYS_ARRAY, TOTAL_PLAYS))
        # (4b) - Expore that keypoint up to some bound
        expiter = 0
        while(expiter != params.VISIT_CONSTANT):
            x, y = sample_from_kp(keypoints[kis])
            try:
                if(((x, y) in params.MANIPULATIONS) or
                   list(image[y][x]) ==
                   list(params.manip_method(image[y][x], params.EPSILON))):
                    continue
            except:
                if(((x, y) in params.MANIPULATIONS) or
                   (image[y][x]) ==
                   (params.manip_method(image[y][x], params.EPSILON))):
                    continue
            image[y][x] = params.manip_method(image[y][x], params.EPSILON)
            params.MANIPULATIONS.append((x, y))
            expiter += 1
        pred, prob = params.predict(image)
        if((pred != int(true_class) and target_class is None) or
           (pred != target_class and target_class is not None)):
            if(params.verbose):
                print("\n")
                print("Adversarial Example Found")
                f = """Current Probability: %s
                       Current Class: %s
                       Manipulations: %s
                    """ % (prob[0][pred], pred, len(params.MANIPULATIONS))
                sys.stdout.write("\r" + str(f))
                sys.stdout.flush()
            MISCLASSIFIED = True
            return keypoint_distribution, image, TOTAL_PLAYS, MISCLASSIFIED
        # !*!
        reward = calculate_reward(params.SOFT_MAX_ARRAY,
                                  prob, true_class, target_class)
        MISCLASSIFIED = False
        if(reward < 0):
            replace = params.MANIPULATIONS[-params.VISIT_CONSTANT:]
            # faster to impliment as a check-point replacement probably
            for x, y in replace:
                image[y][x] = params.ORIGINAL_IMAGE[y][x]
        # (4c) - Backpropogation
        keypoint_distribution = backpropogation(keypoint_distribution,
                                                kis, reward)
        PLAYS_ARRAY[kis] += 1
        TOTAL_PLAYS += 1
        if(params.verbose):
            f = """Current Probability: %s
                   Current Class: %s
                   Manipulations: %s
                """ % (prob[0][pred], pred, len(params.MANIPULATIONS))
            sys.stdout.write("\r" + str(f))
            sys.stdout.flush()
        return keypoint_distribution, image, TOTAL_PLAYS, MISCLASSIFIED
    params.MISCLASSIFIED, mis = False, False
    pred, prob = params.predict(image)
    NEW_PROBABILITY = prob[0][pred]
    params.SOFT_MAX_ARRAY = prob
    if(pred != params.TRUE_CLASS):
        MISCLASSIFIED, mis = True, True
        return params.ORIGINAL_IMAGE, params.SOFT_MAX_ARRAY, 0, None
    iters = 0
    cutoff_enforced = False
    if(params.verbose):
        print("Starting DFMCS. Cuttoff: %s" % (cutoff))
    if(cutoff == -1):
        cutoff_enforced = False
        while(not params.MISCLASSIFIED):
            retvals_from_run = run_mcts_exploitation_step(params.model,
                                                          image,
                                                          params.TRUE_CLASS,
                                                          params.kp,
                                                          params.r,
                                                          backprop,
                                                          params.TOTAL_PLAYS)
            params.r = retvals_from_run[0]
            image = retvals_from_run[1]
            params.TOTAL_PLAYS = retvals_from_run[2]
            params.MISCLASSIFIED = retvals_from_run[3]
            if(params.MISCLASSIFIED):
                break
            retvals_from_run = run_mcts_exploitation_step(params.model,
                                                          image,
                                                          params.TRUE_CLASS,
                                                          params.kp,
                                                          params.r,
                                                          backprop,
                                                          params.TOTAL_PLAYS)
            params.r = retvals_from_run[0]
            image = retvals_from_run[1]
            params.TOTAL_PLAYS = retvals_from_run[2]
            params.MISCLASSIFIED = retvals_from_run[3]
            iters += 1
            # if(iters >= 10):
            # cutoff_enforced = False
            # break
    else:
        cutoff_enforced = True
        for i in range(int(cutoff/int(1.5*params.VISIT_CONSTANT))):
            retvals_from_run = run_mcts_exploitation_step(params.model,
                                                          image,
                                                          params.TRUE_CLASS,
                                                          params.kp,
                                                          params.r,
                                                          backprop,
                                                          params.TOTAL_PLAYS)
            params.r = retvals_from_run[0]
            image = retvals_from_run[1]
            params.TOTAL_PLAYS = retvals_from_run[2]
            params.MISCLASSIFIED = retvals_from_run[3]
            if(params.MISCLASSIFIED):
                cutoff_enforced = False
                break
            retvals_from_run = run_mcts_exploitation_step(params.model,
                                                          image,
                                                          params.TRUE_CLASS,
                                                          params.kp,
                                                          params.r,
                                                          backprop,
                                                          params.TOTAL_PLAYS)
            params.r = retvals_from_run[0]
            image = retvals_from_run[1]
            params.TOTAL_PLAYS = retvals_from_run[2]
            params.MISCLASSIFIED = retvals_from_run[3]
            if(params.MISCLASSIFIED):
                cutoff_enforced = False
                break

    def backtracking(adversarial_image, original_image,
                     manipulations, true_class, cluster=0, target_class=None):
        l_zero = len(manipulations)
        best_bad_example = copy.deepcopy(adversarial_image)
        pixels_at_a_time = cluster
        progress = 0
        for x, y in manipulations:
            if(pixels_at_a_time != 0):
                adversarial_image[y][x] = original_image[y][x]
                pixels_at_a_time -= 1
                continue
            else:
                adversarial_image[y][x] = original_image[y][x]
                pixels_at_a_time = cluster
            pred, prob = params.predict(image)
            if(pred != int(true_class)):
                best_bad_example = copy.deepcopy(adversarial_image)
                l_zero -= (cluster+1)
            else:
                adversarial_image = copy.deepcopy(best_bad_example)
            progress += 1
            if(params.verbose):
                f = """Backtracking Step L_0: %s
                       Probability: %s Class: %s,
                       progress: %s/%s
                    """ % (l_zero, prob[0][pred],
                           pred, progress*cluster, len(manipulations))
                sys.stdout.write("\r" + str(f))
                sys.stdout.flush()
        return best_bad_example, manipulations, l_zero
    # for i in range(10):
    if(params.verbose and not cutoff_enforced):
        print("Backtracking")
    if(cutoff_enforced is False):
        returned_array = backtracking(image,
                                      params.ORIGINAL_IMAGE,
                                      params.MANIPULATIONS,
                                      params.TRUE_CLASS,
                                      cluster=params.backtracking_constant)
        image = returned_array[0]
        params.MANIPULATIONS = returned_array[1]
        l_zero = returned_array[2]
    if(params.verbose and not cutoff_enforced):
        print("\n Done backtracking")
    pred, prob = params.predict(image)
    # Output: adv_image, softmax_array, L0 Severity, kp_selection
    if(cutoff_enforced):
        return image, prob,  -1, params.r
    else:
        return image, prob,  l_zero, params.r
