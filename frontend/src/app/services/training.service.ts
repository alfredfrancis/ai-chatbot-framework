import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../environments/environment';

@Injectable()
export class TrainingService {

  constructor(public http: HttpClient) {}

  saveTrainingData(intent_id,data) {
    return this.http.post(environment.ikyBackend + `train/${intent_id}/data`, data).toPromise();
  }

  getTrainingData(intent_id) {
    return this.http.get(environment.ikyBackend + `train/${intent_id}/data`).toPromise();
  }

  trainModels() {
    return this.http.post(environment.ikyBackend + `nlu/build_models`, {}).toPromise();
  }

}


