import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../environments/environment';

@Injectable()
export class IntentService {
  public static intentTypes = {
    'mobile': 'Mobile number',
    'email': 'Email',
    'free_text': 'Free Text',
    'number': 'Number',
    'list': 'List',
  };

  constructor(public http: HttpClient) {
  }

  getIntents() {
    return this.http.get(environment.ikyBackend + 'intents/').toPromise();
  }

  getIntent(id) {
    return this.http.get(environment.ikyBackend + `intents/${id}`).toPromise();
  }

  saveIntent(intent) {
    if (intent._id) {
      return this.update_intent(intent);
    } else {
      delete intent._id;
      return this.create_intent(intent);
    }
  }

  create_intent(intent) {
    return this.http.post(environment.ikyBackend + `intents/`, intent).toPromise();
  }

  update_intent(intent) {
    return this.http.put(environment.ikyBackend + `intents/${intent._id}`, intent).toPromise();
  }

  delete_intent(id) {
    return this.http.delete(environment.ikyBackend + `intents/${id}`, {}).toPromise();
  }

  importIntents(fileToUpload: File){
    const formData: FormData = new FormData();
    formData.append('file', fileToUpload, fileToUpload.name);
    return this.http
      .post(environment.ikyBackend +"intents/import", formData).toPromise();
  }

}

