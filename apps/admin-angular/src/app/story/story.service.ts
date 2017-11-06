import { Injectable } from '@angular/core';
import { Http, RequestOptions } from '@angular/http';
import { CoreService } from '../core/core.service';

@Injectable()
export class StoryService extends CoreService {

  constructor(public http: Http) {
    super(http);
  }

  getStories() {
    return this.doGet(`/stories/`);
  }

  getStory(id) {
    return this.doGet(`/stories/edit/${id}`);
  }

  updateStory(id) {
    return this.doPut(`/stories/${id}`, {});
  }

  buildStory(id) {
    return this.doPost(`/core/buildModel/${id}`, {});
  }

  deleteStory(id) {
    return this.doDelete(`/stories/${id}`, {});
  }

  /**
   * 
   * @param sentences ex.: i'm searching product
   */
  startLabeling(sentences) {
    return this.doPost(`/core/posTagAndLabel`, {sentences});
  }

/**
 * 
 * @param storyId  ex.:59fddff51ec5e81bf9d6e021
 * @param labeledSentence   ex.: [["i","NN","O"],["'m","VBP","O"],["searching","VBG","O"],["product","NN","O"]] 
 */
  addToTestSet(storyId, labeledSentence) {
    return this.doPost(`/train/insertLabeledSentence`, {storyId, labeledSentence});
  }

}
