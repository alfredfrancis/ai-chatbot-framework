import html2text

from flask import Blueprint, request

from app.commons import buildResponse
import app.core.nlp as nlp


from app.stories.models import Story
from bson.objectid import ObjectId


core = Blueprint('core_blueprint', __name__, url_prefix='/core')


from app.core.tasks import train_models

@core.route('/buildModels', methods=['POST'])
def buildModels():
    train_models()
    return buildResponse.sentOk()


@core.route('/sentenceTokenize', methods=['POST'])
def sentenceTokenize():
    sentences = html2text.html2text(request.form['sentences'])
    result = nlp.sentenceTokenize(sentences)
    return buildResponse.sentPlainText(result)


@core.route('/posTagAndLabel', methods=['POST'])
def posTagAndLabel():
    sentences = request.form['sentences']
    cleanSentences = html2text.html2text(sentences)
    result = nlp.posTagAndLabel(cleanSentences)
    return buildResponse.buildJson(result)


def prepare_training_data(storyId):
    """
    Reference function
    :param storyId:
    :return:
    """
    story = Story.objects.get(id=ObjectId(storyId))
    labeled_examples = []

    for example in story.trainingData:
        tagged_example = nlp.posTagAndLabel(example.get("text"))


        print(tagged_example)


        for enitity in example.get("entities"):
            print(enitity.get("begin"),enitity.get("end"))
            word_count = 0
            char_count = 0
            for i,item in enumerate(tagged_example):
                char_count += len(item[0])
                if enitity.get("begin") == 0:
                    word_count = 0
                    break
                elif char_count == enitity.get("begin"):
                    word_count += 1
                    break
                elif  char_count < enitity.get("begin"):
                    word_count += 1
                else:
                    break
            print(word_count)



            selection = example.get("text")[enitity.get("begin"):enitity.get("end")]
            tokens = nlp.sentenceTokenize(selection).split(" ")
            selection_word_count = len(tokens)
            print("selection count %d"%selection_word_count)

            for i in range(1, selection_word_count+1):
                print("word "+str(i))
                if i ==1:
                    bio = "B-" + enitity.get("name")
                else:
                    bio = "I-" + enitity.get("name")
                print(bio)
                tagged_example[(word_count + i) - 1][2] = bio

        labeled_examples.append(tagged_example)


    print (labeled_examples)
    return buildResponse.buildJson(labeled_examples)
