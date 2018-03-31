import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../environments/environment';

@Injectable()
export class IntentService {
  public static storyTypes = {
    'mobile': 'Mobile number',
    'email': 'Email',
    'free_text': 'Free Text',
    'number': 'Number',
    'list': 'List',
  };

  constructor(public http: HttpClient) {
  }

  getStories() {
    return this.http.get(environment.ikyBackend + 'stories/').toPromise();
  }

  getStory(id) {
    return this.http.get(environment.ikyBackend + `stories/${id}`).toPromise();
  }

  saveStory(story) {
    if (story._id) {
      return this.updateStory(story);
    } else {
      delete story._id;
      return this.createStory(story);
    }
  }

  createStory(story) {
    return this.http.post(environment.ikyBackend + `stories/`, story).toPromise();
  }

  updateStory(story) {
    return this.http.put(environment.ikyBackend + `stories/${story._id}`, story).toPromise();
  }

  buildStory(id) {
    return this.http.post(environment.ikyBackend + `core/buildModel/${id}`, {}).toPromise();
  }

  deleteStory(id) {
    return this.http.delete(environment.ikyBackend + `stories/${id}`, {}).toPromise();
  }

  /**
   *
   * @param sentences ex.: i'm searching product
   */
  startLabeling(sentences) {
    return this.http.post(environment.ikyBackend + `core/posTagAndLabel?json=true`, { sentences }).toPromise();
  }

  /**
   *
   * @param storyId  ex.:59fddff51ec5e81bf9d6e021
   * @param labeledSentence   ex.: [["i","NN","O"],["'m","VBP","O"],["searching","VBG","O"],["product","NN","O"]]
   */
  addToTestSet(storyId, labeledSentence, botId = 'default') {
    return this.http.post(environment.ikyBackend + `train/insertLabeledSentence`, { storyId, botId, labeledSentence }).toPromise();
  }
}

