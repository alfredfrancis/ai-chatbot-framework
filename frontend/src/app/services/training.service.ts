import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../environments/environment';

@Injectable()
export class TrainingService {

  constructor(public http: HttpClient) {}
  
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
  
  saveTrainingData(intent_id,data) {
    return this.http.post(environment.ikyBackend + `train/${intent_id}/data`, data).toPromise();
  }

  getTrainingData(intent_id) {
    return this.http.get(environment.ikyBackend + `train/${intent_id}/data`).toPromise();
  }

  trainModels() {
    return this.http.post(environment.ikyBackend + `core/buildModels`, {}).toPromise();
  }

}


